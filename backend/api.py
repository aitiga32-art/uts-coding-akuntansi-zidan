"""Alternatif API HTTP. Streamlit memakai service Python yang sama secara langsung."""
import os
import secrets
from datetime import date
from decimal import Decimal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from backend import service


def authenticate(authorization: str = Header(default="")):
    token = os.getenv("API_TOKEN", "")
    if not token:
        raise HTTPException(503, "API_TOKEN belum dikonfigurasi")
    if not secrets.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "Token tidak valid")


app = FastAPI(title="Voucher Akuntansi Zidan", version="1.0.0", dependencies=[Depends(authenticate)])


class Line(BaseModel):
    account_id: int = Field(gt=0)
    debit: Decimal = Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)
    credit: Decimal = Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)


class Voucher(BaseModel):
    transaction_date: date
    reference_no: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    lines: list[Line] = Field(min_length=2, max_length=100)


class Reversal(BaseModel):
    transaction_date: date
    reference_no: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1)


class StockTransaction(BaseModel):
    item_id: str
    trx_type: str
    qty: int
    reference_no: str = Field(min_length=1, max_length=76)
    reason: str = Field(min_length=1)


def execute(call):
    try:
        return {"id": call(), "status": "POSTED"}
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise HTTPException(409, service.error_message(exc)) from None


@app.post("/vouchers", status_code=201)
def create_voucher(body: Voucher):
    return execute(lambda: service.submit_voucher(body.transaction_date, body.reference_no,
        body.description, [line.model_dump() for line in body.lines]))


@app.post("/journals/{journal_id}/reverse", status_code=201)
def reverse_journal(journal_id: int, body: Reversal):
    return execute(lambda: service.reverse(journal_id, body.transaction_date, body.reference_no, body.reason))


@app.post("/inventory", status_code=201)
def record_stock(body: StockTransaction):
    return execute(lambda: service.inventory(body.item_id, body.trx_type, body.qty, body.reference_no, body.reason))


@app.get("/journals")
def list_journals():
    return service.journals()


@app.get("/journals/{journal_id}/integrity")
def integrity(journal_id: int):
    result = service.read("SELECT accounting.verify_journal(%s) AS valid", (journal_id,))[0]
    if result["valid"] is None:
        raise HTTPException(404, "Jurnal tidak ditemukan")
    return result


@app.put("/journals/{journal_id}")
@app.delete("/journals/{journal_id}")
def immutable(journal_id: int):
    raise HTTPException(405, "Gunakan endpoint reversal untuk mengoreksi jurnal POSTED")
