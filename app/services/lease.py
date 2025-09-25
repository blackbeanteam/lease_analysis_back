import uuid
from typing import Dict, Any

def analyze_pdf_bytes(filename: str, data: bytes) -> Dict[str, Any]:
    # 这里先做个假结果；以后把真实解析逻辑接进来即可
    return {
        "id": uuid.uuid4().hex,
        "filename": filename,
        "size_bytes": len(data),
        "schema_version": "1.0",
        "summary": {
          "verdict": "conditional_ok",
          "risk_score": 5,
          "jurisdiction": {
            "country": "United States",
            "state": "Massachusetts",
            "city": "Malden"
        },
          "notes": "The lease contains several provisions that may require further review for compliance with Massachusetts landlord-tenant laws."
        },
        "findings": [
          {
            "id": "1",
            "status": "ok",
            "severity": "low",
            "category": "money_dates",
            "statutes": [],
            "explanation": "The lease specifies the rent amount and payment due date, which is compliant with Massachusetts law.",
            "recommendation": "Ensure timely payment of rent as specified.",
            "original_text": "The Resident agrees to pay monthly Rent, as specified in Exhibit I. Rent shall be paid in advance on or before the first day of each month.",
            "evidence": [],
            "checks": [],
            "tags": [],
            "notes": "",
            "extensions": {},
            "low_confidence": False
          },
          {
            "id": "2",
            "status": "needs_detail",
            "severity": "medium",
            "category": "deposit_return",
            "statutes": ["STATE statute on security deposit return"],
            "explanation": "The lease states that the security deposit will be returned within 30 days after termination, which aligns with Massachusetts law, but lacks specific details on interest payment.",
            "recommendation": "Clarify the interest payment terms for the security deposit.",
            "original_text": "The Manager shall, within thirty (30) days after termination of this Lease... return said Security Deposit or any balance thereof, and any interest thereon, as required by law.",
            "evidence": [],
            "checks": [],
            "tags": [],
            "notes": "",
            "extensions": {},
            "low_confidence": True
          },
          {
            "id": "3",
            "status": "ok",
            "severity": "low",
            "category": "renewal",
            "statutes": [],
            "explanation": "The lease includes a provision for automatic renewal, which is compliant with Massachusetts law as long as proper notice is given.",
            "recommendation": "Provide written notice of non-renewal at least 60 days prior to expiration.",
            "original_text": "This Lease shall automatically renew for successive twelve (12) month terms... unless written notice of non-renewal is issued by either party to the other party at least sixty (60) days prior to expiration.",
            "evidence": [],
            "checks": [],
            "tags": [],
            "notes": "",
            "extensions": {},
            "low_confidence": False
          },
          {
            "id": "4",
            "status": "non_compliant",
            "severity": "high",
            "category": "termination",
            "statutes": ["STATE statute on notice for termination"],
            "explanation": "The lease allows for a 7-day notice for termination due to breach, which may not comply with Massachusetts law requiring a longer notice period for non-payment of rent.",
            "recommendation": "Revise the termination notice period to comply with Massachusetts law.",
            "original_text": "the Manager, without the necessity or requirement of making any entry, may... declare the Resident to be in default... a seven (7) day written notice to the Resident to vacate said Premises in case of any breach except for nonpayment of Rent.",
            "evidence": [],
            "checks": [],
            "tags": [],
            "notes": "",
            "extensions": {},
            "low_confidence": True
          },
          {
            "id": "5",
            "status": "ok",
            "severity": "low",
            "category": "repairs_entry",
            "statutes": [],
            "explanation": "The lease provides for reasonable notice before entry for repairs, which is compliant with Massachusetts law.",
            "recommendation": "Maintain a record of notices given for entry.",
            "original_text": "The Manager may enter upon the Premises at reasonable times with notice to examine the condition thereof, show the Premises to prospective purchasers, residents, or mortgagees, or to make repairs thereto.",
            "evidence": [],
            "checks": [],
            "tags": [],
            "notes": "",
            "extensions": {},
            "low_confidence": False
          }
        ]
    }
