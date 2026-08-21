import re
import operator
from typing import Optional

# Word to number mapping for textual captchas (e.g., "five plus seven")
WORD_TO_NUM = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
    'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
    'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
    'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
    'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
    'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100
}

OPERATORS = {
    '+': operator.add,
    'plus': operator.add,
    'add': operator.add,
    '-': operator.sub,
    'minus': operator.sub,
    'subtract': operator.sub,
    '*': operator.mul,
    'x': operator.mul,
    'times': operator.mul,
    'multiply': operator.mul,
    'multiplied by': operator.mul,
    '/': operator.floordiv,
    'divided by': operator.floordiv,
    'divide': operator.floordiv,
}


def _token_to_number(token: str) -> Optional[int]:
    """Convert a digit string or word into an integer."""
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    if token in WORD_TO_NUM:
        return WORD_TO_NUM[token]
    if '-' in token:
        parts = token.split('-')
        if len(parts) == 2 and parts[0] in WORD_TO_NUM and parts[1] in WORD_TO_NUM:
            return WORD_TO_NUM[parts[0]] + WORD_TO_NUM[parts[1]]
    return None


class NumericalCaptchaSolver:
    """
    Parser and solver for arithmetic and numerical CAPTCHAs.
    Examples handled:
      - "2 + 7" -> 9
      - "Captcha7 + 8 = ?" -> 15
      - "Captcha 9 - 6 = ?" -> 3
      - "15 - 4 =" -> 11
      - "What is 3 * 8 ?" -> 24
      - "Calculate 20 divided by 4" -> 5
      - "five plus six" -> 11
    """

    @classmethod
    def solve(cls, text: str) -> Optional[int]:
        """
        Extract and solve an arithmetic expression from raw text/HTML.
        Returns the integer solution, or None if no valid math problem was detected.
        """
        if not text:
            return None

        # Clean text
        clean_text = text.replace('=', ' ').replace('?', ' ').replace(':', ' ').strip()

        # 1. Pure Digit Arithmetic Pattern (e.g. "Captcha7 + 8", "12 - 4", "3 * 9")
        pattern_digits = re.compile(
            r'(\d+)\s*([\+\-\*\/x]|plus|minus|times|multiplied\s+by|divided\s+by|divide)\s*(\d+)',
            re.IGNORECASE
        )
        match_digits = pattern_digits.search(clean_text)
        if match_digits:
            n1_str, op_str, n2_str = match_digits.groups()
            n1 = int(n1_str)
            n2 = int(n2_str)
            op_key = op_str.strip().lower()
            op_func = OPERATORS.get(op_key)
            if op_func:
                try:
                    return op_func(n1, n2)
                except ZeroDivisionError:
                    return 0

        # 2. Word & Digit Mixed Pattern: <token1> <op> <token2> (e.g. "five plus seven", "14 minus four")
        pattern_tokens = re.compile(
            r'(\b[a-zA-Z0-9\-]+\b)\s*([\+\-\*\/x]|plus|minus|times|multiplied\s+by|divided\s+by|divide)\s*(\b[a-zA-Z0-9\-]+\b)',
            re.IGNORECASE
        )
        match_tokens = pattern_tokens.search(clean_text)
        if match_tokens:
            num1_str, op_str, num2_str = match_tokens.groups()
            num1 = _token_to_number(num1_str)
            num2 = _token_to_number(num2_str)
            op_key = op_str.strip().lower()

            if num1 is not None and num2 is not None:
                op_func = OPERATORS.get(op_key)
                if op_func:
                    try:
                        return op_func(num1, num2)
                    except ZeroDivisionError:
                        return 0

        # 3. Textual pattern: "sum of X and Y" or "add X and Y"
        pattern_sum = re.compile(
            r'(?:sum\s+of|add)\s+(\b\w+\b)\s+(?:and|\+)\s+(\b\w+\b)',
            re.IGNORECASE
        )
        match_sum = pattern_sum.search(clean_text)
        if match_sum:
            num1 = _token_to_number(match_sum.group(1))
            num2 = _token_to_number(match_sum.group(2))
            if num1 is not None and num2 is not None:
                return num1 + num2

        # 4. Textual pattern: "subtract X from Y" -> Y - X
        pattern_sub_from = re.compile(
            r'subtract\s+(\b\w+\b)\s+from\s+(\b\w+\b)',
            re.IGNORECASE
        )
        match_sub_from = pattern_sub_from.search(clean_text)
        if match_sub_from:
            num1 = _token_to_number(match_sub_from.group(1))
            num2 = _token_to_number(match_sub_from.group(2))
            if num1 is not None and num2 is not None:
                return num2 - num1

        # 5. Textual pattern: "difference between X and Y" -> abs(X - Y)
        pattern_diff = re.compile(
            r'difference\s+between\s+(\b\w+\b)\s+and\s+(\b\w+\b)',
            re.IGNORECASE
        )
        match_diff = pattern_diff.search(clean_text)
        if match_diff:
            num1 = _token_to_number(match_diff.group(1))
            num2 = _token_to_number(match_diff.group(2))
            if num1 is not None and num2 is not None:
                return abs(num1 - num2)

        # 6. Textual pattern: "product of X and Y" -> X * Y
        pattern_prod = re.compile(
            r'product\s+of\s+(\b\w+\b)\s+and\s+(\b\w+\b)',
            re.IGNORECASE
        )
        match_prod = pattern_prod.search(clean_text)
        if match_prod:
            num1 = _token_to_number(match_prod.group(1))
            num2 = _token_to_number(match_prod.group(2))
            if num1 is not None and num2 is not None:
                return num1 * num2

        return None
