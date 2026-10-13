from decimal import Decimal, InvalidOperation


def money(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Nominal harus berupa angka.") from None
    if not result.is_finite() or result < 0 or result >= Decimal("10000000000000000"):
        raise ValueError("Nominal harus positif/nol dan berada dalam batas database.")
    if result != result.quantize(Decimal("0.01")):
        raise ValueError("Nominal maksimal dua angka desimal.")
    return result


def validate_lines(lines):
    if not 2 <= len(lines) <= 100:
        raise ValueError("Jurnal harus memiliki 2 sampai 100 baris.")
    debit = Decimal("0.00")
    credit = Decimal("0.00")
    clean = []
    for row in lines:
        d, c = money(row.get("debit")), money(row.get("credit"))
        if (d > 0) == (c > 0):
            raise ValueError("Setiap baris harus berisi tepat satu sisi debit atau kredit.")
        try:
            account = int(row["account_id"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Pilih akun untuk setiap baris.") from None
        if account <= 0 or str(row["account_id"]) not in (str(account), f"{account}.0"):
            raise ValueError("ID akun tidak valid.")
        clean.append({"account_id": account, "debit": str(d), "credit": str(c)})
        debit += d
        credit += c
    if debit != credit:
        raise ValueError("Total debit harus sama dengan total kredit.")
    return clean, debit, credit
