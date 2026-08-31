from sqlalchemy.exc import IntegrityError
import pytest

from app.models import PayPeriod, Payslip


def test_duplicate_payslip_hash_is_rejected_by_database(db) -> None:
    first = PayPeriod()
    second = PayPeriod()
    first.payslip = Payslip(file_hash="a" * 64)
    second.payslip = Payslip(file_hash="a" * 64)
    db.add_all([first, second])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

