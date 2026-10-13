import unittest
from decimal import Decimal
from backend.validation import money, validate_lines


class ValidationTests(unittest.TestCase):
    def test_decimal_exact(self):
        _,d,c=validate_lines([{"account_id":1,"debit":"0.10","credit":0},
            {"account_id":2,"debit":"0.20","credit":0},{"account_id":3,"debit":0,"credit":"0.30"}])
        self.assertEqual(d,c)
        self.assertEqual(d,Decimal("0.30"))

    def test_bad_money(self):
        for value in [None,"NaN","Infinity","-1","0.001","abc"]:
            with self.subTest(value=value), self.assertRaises(ValueError): money(value)

    def test_zero_or_both_sides(self):
        for d,c in [(0,0),(1,1)]:
            with self.subTest(d=d,c=c),self.assertRaises(ValueError):
                validate_lines([{"account_id":1,"debit":d,"credit":c}]*2)

    def test_unbalanced(self):
        with self.assertRaises(ValueError):
            validate_lines([{"account_id":1,"debit":5,"credit":0},{"account_id":2,"debit":0,"credit":4}])

    def test_invalid_account(self):
        with self.assertRaises(ValueError):
            validate_lines([{"account_id":None,"debit":5,"credit":0},{"account_id":2,"debit":0,"credit":5}])
