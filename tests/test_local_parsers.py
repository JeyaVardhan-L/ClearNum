"""Tests for local MBOX email archive and SMS backup parsing."""

import pytest
from pathlib import Path
import mailbox
from email.message import EmailMessage
from backend.app.engines.discovery.local_parsers.mbox_parser import parse_mbox_file
from backend.app.engines.discovery.local_parsers.sms_parser import parse_sms_backup_file
from backend.app.engines.discovery.normalizer import parse_and_normalize


def test_mbox_parser_extracts_subscriptions(tmp_path: Path):
    mbox_file = tmp_path / "test_inbox.mbox"
    mb = mailbox.mbox(str(mbox_file))

    # Add marketing email with List-Unsubscribe header
    msg1 = EmailMessage()
    msg1["From"] = "Retail Deals <deals@shoponline.example.com>"
    msg1["Subject"] = "Exclusive Summer Sale"
    msg1["List-Unsubscribe"] = "<https://shoponline.example.com/unsub/user123>, <mailto:unsub@shoponline.example.com>"
    msg1.set_content("Check out our sales today! Unsubscribe at any time.")
    mb.add(msg1)

    # Add email with target phone number exposed in signature
    msg2 = EmailMessage()
    msg2["From"] = "Colleague <alice@company.example.com>"
    msg2["Subject"] = "Updated contact details"
    msg2.set_content("Please call me or text my direct cell: (415) 555-2671 when free.")
    mb.add(msg2)

    mb.flush()
    mb.close()

    phone = parse_and_normalize("+14155552671", "US")
    subs = parse_mbox_file(mbox_file, phone=phone)

    assert len(subs) >= 1
    # Check unsubscribe header captured
    deals_sub = next((s for s in subs if "deals@shoponline.example.com" in s.sender_contact), None)
    assert deals_sub is not None
    assert deals_sub.unsubscribe_method == "HEADER_URL"
    assert "shoponline.example.com/unsub" in deals_sub.unsubscribe_target


def test_sms_backup_xml_parser(tmp_path: Path):
    xml_file = tmp_path / "sms_backup.xml"
    xml_content = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <smses count="3">
        <sms address="223344" body="Your coupon code is SAVE20. Reply STOP to cancel." date="1700000000000" type="1" />
        <sms address="223344" body="Flash sale ending in 2 hours. Reply STOP to opt out." date="1700003600000" type="1" />
        <sms address="18005550199" body="Your delivery has arrived." date="1700007200000" type="1" />
    </smses>
    """
    xml_file.write_text(xml_content, encoding="utf-8")

    senders = parse_sms_backup_file(xml_file)
    assert len(senders) == 2

    shortcode_sender = next((s for s in senders if s.sender_number == "223344"), None)
    assert shortcode_sender is not None
    assert shortcode_sender.is_shortcode is True
    assert shortcode_sender.message_count == 2
    assert shortcode_sender.has_opt_out_keyword is True
    assert shortcode_sender.opt_out_command == "STOP"
    assert shortcode_sender.category == "MARKETING_SMS"


def test_sms_dlt_headers_and_single_analyzer(tmp_path: Path):
    from backend.app.engines.discovery.local_parsers.sms_parser import analyze_single_sms

    # 1. Test XML with DLT headers
    xml_file = tmp_path / "dlt_sms_backup.xml"
    xml_content = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <smses count="4">
        <sms address="VM-HDFCBK" body="Avail pre-approved personal loan at 9.9%. Reply STOP to opt out." date="1700000000000" type="1" />
        <sms address="AD-SWIGGY" body="50% off on your favourite meals on Swiggy today!" date="1700001000000" type="1" />
        <sms address="VK-AMAZON" body="Great Indian Festival deals live now on Amazon." date="1700002000000" type="1" />
        <sms address="CP-AIRTEL" body="Recharge your Airtel prepaid number for unlimited data." date="1700003000000" type="1" />
    </smses>
    """
    xml_file.write_text(xml_content, encoding="utf-8")

    senders = parse_sms_backup_file(xml_file)
    assert len(senders) == 4

    hdfc = next((s for s in senders if s.sender_number == "VM-HDFCBK"), None)
    assert hdfc is not None
    assert hdfc.brand_name == "HDFCBK"
    assert hdfc.dlt_prefix == "VM"
    assert hdfc.category == "COMMERCIAL_BANKING"
    assert hdfc.has_opt_out_keyword is True

    swiggy = next((s for s in senders if s.sender_number == "AD-SWIGGY"), None)
    assert swiggy is not None
    assert swiggy.brand_name == "SWIGGY"
    assert swiggy.category == "COMMERCIAL_SHOPPING"

    airtel = next((s for s in senders if s.sender_number == "CP-AIRTEL"), None)
    assert airtel is not None
    assert airtel.brand_name == "AIRTEL"
    assert airtel.category == "COMMERCIAL_TELECOM"

    # 2. Test single message analyzer
    single = analyze_single_sms("AD-SWIGGY", "50% off on your food order with Swiggy", "IN")
    assert single.brand_name == "SWIGGY"
    assert single.category == "COMMERCIAL_SHOPPING"
    assert "TRAI 1909" in single.recommended_action
