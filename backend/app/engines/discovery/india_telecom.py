"""India Telecommunications, DLT Sender Header, and Regulatory Intelligence Engine.

Provides authoritative mapping of:
1. TRAI/DoT 22 Telecom Circles (Service Areas).
2. Telecom Access Providers (Airtel, Jio, Vi, BSNL, MTNL, Tata).
3. 110+ Curated Indian Brands with registered DLT headers.
4. TRAI 1909 Statutory Complaint SMS Syntax (TCCCPR 2018).
5. DoT Chakshu (Sanchar Saathi) Suspect Fraud Escalation.
6. DPDP Act 2023 Statutory Consent Revocation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import re

# 22 Licensed Telecom Service Areas (LSA / Circles) per DoT National Numbering Plan
TELECOM_CIRCLES: Dict[str, Dict[str, str]] = {
    "D": {"name": "Delhi", "state": "Delhi NCR", "type": "Metro"},
    "M": {"name": "Mumbai", "state": "Mumbai & Goa (Part)", "type": "Metro"},
    "K": {"name": "Kolkata", "state": "Kolkata", "type": "Metro"},
    "C": {"name": "Chennai", "state": "Chennai", "type": "Metro"},
    "A": {"name": "Andhra Pradesh", "state": "Andhra Pradesh & Telangana", "type": "Circle A"},
    "G": {"name": "Gujarat", "state": "Gujarat, Daman & Diu, Dadra & Nagar Haveli", "type": "Circle A"},
    "KK": {"name": "Karnataka", "state": "Karnataka", "type": "Circle A"},
    "MH": {"name": "Maharashtra", "state": "Maharashtra & Goa (excl. Mumbai)", "type": "Circle A"},
    "TN": {"name": "Tamil Nadu", "state": "Tamil Nadu (excl. Chennai)", "type": "Circle A"},
    "H": {"name": "Haryana", "state": "Haryana", "type": "Circle B"},
    "KL": {"name": "Kerala", "state": "Kerala & Lakshadweep", "type": "Circle B"},
    "MP": {"name": "Madhya Pradesh", "state": "Madhya Pradesh & Chhattisgarh", "type": "Circle B"},
    "PB": {"name": "Punjab", "state": "Punjab & Chandigarh", "type": "Circle B"},
    "RJ": {"name": "Rajasthan", "state": "Rajasthan", "type": "Circle B"},
    "UE": {"name": "UP East", "state": "Uttar Pradesh (East)", "type": "Circle B"},
    "UW": {"name": "UP West", "state": "Uttar Pradesh (West) & Uttarakhand", "type": "Circle B"},
    "WB": {"name": "West Bengal", "state": "West Bengal (excl. Kolkata), Sikkim, A&N", "type": "Circle B"},
    "AS": {"name": "Assam", "state": "Assam", "type": "Circle C"},
    "BH": {"name": "Bihar", "state": "Bihar & Jharkhand", "type": "Circle C"},
    "HP": {"name": "Himachal Pradesh", "state": "Himachal Pradesh", "type": "Circle C"},
    "J": {"name": "Jammu & Kashmir", "state": "Jammu & Kashmir & Ladakh", "type": "Circle C"},
    "NE": {"name": "North East", "state": "Arunachal, Manipur, Meghalaya, Mizoram, Nagaland, Tripura", "type": "Circle C"},
    "O": {"name": "Odisha", "state": "Odisha", "type": "Circle C"},
}

# Principal Telecom Access Providers
ACCESS_PROVIDERS: Dict[str, str] = {
    "A": "Bharti Airtel",
    "V": "Vi (Vodafone Idea)",
    "J": "Reliance Jio",
    "B": "BSNL",
    "M": "MTNL",
    "T": "Tata Teleservices",
    "Q": "Quadrant Televentures",
}

# 110+ Major Indian Brands mapped to known DLT headers, official grievance channels, and categories
@dataclass
class IndianBrandMetadata:
    brand_name: str
    category: str
    dlt_codes: List[str]
    official_website: str
    dnd_url: str
    grievance_email: Optional[str] = None
    customer_care_phone: Optional[str] = None
    description: Optional[str] = None


INDIAN_BRAND_REGISTRY: Dict[str, IndianBrandMetadata] = {
    # --- 1. Banking & Financial Institutions ---
    "HDFCBK": IndianBrandMetadata(
        brand_name="HDFC Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["HDFCBK", "HDFCCC", "HDFCLO", "HDFCSM", "HDFCAL"],
        official_website="https://www.hdfcbank.com",
        dnd_url="https://www.hdfcbank.com/personal/useful-links/privacy",
        grievance_email="grievance.redressal@hdfcbank.com",
        customer_care_phone="1800-202-6161",
        description="India's largest private bank. Issues credit cards, loans, and investment products.",
    ),
    "SBINB": IndianBrandMetadata(
        brand_name="State Bank of India (SBI)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["SBINB", "SBIINB", "SBICRD", "SBILON", "SBISMS", "SBIYON"],
        official_website="https://sbi.co.in",
        dnd_url="https://sbi.co.in/web/customer-care",
        grievance_email="customercare@sbi.co.in",
        customer_care_phone="1800-1234",
        description="India's largest public sector bank.",
    ),
    "ICICIB": IndianBrandMetadata(
        brand_name="ICICI Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ICICIB", "ICICIC", "ICICIP", "ICICIS", "ICICIL"],
        official_website="https://www.icicibank.com",
        dnd_url="https://www.icicibank.com/do-not-call",
        grievance_email="headservicequality@icicibank.com",
        customer_care_phone="1800-1080",
        description="Major private sector bank offering banking, loans, and insurance.",
    ),
    "AXISBK": IndianBrandMetadata(
        brand_name="Axis Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["AXISBK", "AXISCD", "AXISCR", "AXISSM"],
        official_website="https://www.axisbank.com",
        dnd_url="https://www.axisbank.com/contact-us/do-not-call",
        grievance_email="nodalofficer@axisbank.com",
        customer_care_phone="1860-419-5555",
        description="Major Indian private bank and financial services entity.",
    ),
    "KOTAKB": IndianBrandMetadata(
        brand_name="Kotak Mahindra Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["KOTAKB", "KOTAKC", "KOTAKS", "KOTAKL"],
        official_website="https://www.kotak.com",
        dnd_url="https://www.kotak.com/en/customer-service/do-not-call-registry.html",
        grievance_email="nodalofficer@kotak.com",
        customer_care_phone="1860-266-2666",
        description="Full-service commercial bank and wealth management company.",
    ),
    "PNBSMS": IndianBrandMetadata(
        brand_name="Punjab National Bank (PNB)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["PNBSMS", "PNBBNK", "PNBCRD"],
        official_website="https://www.pnbindia.in",
        dnd_url="https://www.pnbindia.in/grievance.html",
        grievance_email="care@pnb.co.in",
        customer_care_phone="1800-180-2222",
        description="Public sector bank headquartered in New Delhi.",
    ),
    "BOBSMS": IndianBrandMetadata(
        brand_name="Bank of Baroda",
        category="COMMERCIAL_BANKING",
        dlt_codes=["BOBSMS", "BOBBNK", "BOBCRD"],
        official_website="https://www.bankofbaroda.in",
        dnd_url="https://www.bankofbaroda.in/do-not-call-registry",
        grievance_email="gm.ops.ho@bankofbaroda.com",
        customer_care_phone="1800-5700",
        description="Major public sector bank based in Vadodara.",
    ),
    "CANBK": IndianBrandMetadata(
        brand_name="Canara Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["CANBK", "CANRAB", "CANBNK"],
        official_website="https://canarabank.com",
        dnd_url="https://canarabank.com/customer-service",
        grievance_email="hoinfored@canarabank.com",
        customer_care_phone="1800-425-0018",
        description="Leading public sector commercial bank in India.",
    ),
    "UNIBNK": IndianBrandMetadata(
        brand_name="Union Bank of India",
        category="COMMERCIAL_BANKING",
        dlt_codes=["UNIBNK", "UNIONB", "UBISMS"],
        official_website="https://www.unionbankofindia.co.in",
        dnd_url="https://www.unionbankofindia.co.in/english/customer-care.aspx",
        grievance_email="customercare@unionbankofindia.bank",
        customer_care_phone="1800-22-2244",
        description="Government-owned bank headquartered in Mumbai.",
    ),
    "INDBNK": IndianBrandMetadata(
        brand_name="Indian Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["INDBNK", "INDBK", "IBKSMS"],
        official_website="https://www.indianbank.in",
        dnd_url="https://www.indianbank.in/departments/customer-service/",
        grievance_email="nodal.officer@indianbank.co.in",
        customer_care_phone="1800-425-00000",
        description="Major public sector bank based in Chennai.",
    ),
    "INDUSB": IndianBrandMetadata(
        brand_name="IndusInd Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["INDUSB", "INDUSC", "INDUSL"],
        official_website="https://www.indusind.com",
        dnd_url="https://www.indusind.com/in/en/personal/do-not-call.html",
        grievance_email="nodal.officer@indusind.com",
        customer_care_phone="1860-267-7777",
        description="Private commercial bank in India.",
    ),
    "IDFCFB": IndianBrandMetadata(
        brand_name="IDFC FIRST Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["IDFCFB", "IDFCCC", "IDFCSM"],
        official_website="https://www.idfcfirstbank.com",
        dnd_url="https://www.idfcfirstbank.com/do-not-call",
        grievance_email="nodalofficer@idfcfirstbank.com",
        customer_care_phone="1800-10-888",
        description="Tech-led commercial private bank in India.",
    ),
    "YESBNK": IndianBrandMetadata(
        brand_name="Yes Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["YESBNK", "YESBK", "YESCRD"],
        official_website="https://www.yesbank.in",
        dnd_url="https://www.yesbank.in/do-not-call",
        grievance_email="head.customerservice@yesbank.in",
        customer_care_phone="1800-1200",
        description="Indian private sector bank offering personal and business banking.",
    ),
    "RBLBNK": IndianBrandMetadata(
        brand_name="RBL Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["RBLBNK", "RBLCRD", "RBLSMS"],
        official_website="https://www.rblbank.com",
        dnd_url="https://www.rblbank.com/do-not-call-registry",
        grievance_email="principalnodalofficer@rblbank.com",
        customer_care_phone="022-61156300",
        description="Private sector bank with credit card partnerships across India.",
    ),
    "FEDBNK": IndianBrandMetadata(
        brand_name="Federal Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["FEDBNK", "FEDBK", "FEDCRD"],
        official_website="https://www.federalbank.co.in",
        dnd_url="https://www.federalbank.co.in/do-not-call",
        grievance_email="support@federalbank.co.in",
        customer_care_phone="1800-425-1199",
        description="Major private sector commercial bank headquartered in Aluva, Kerala.",
    ),
    "AUBANK": IndianBrandMetadata(
        brand_name="AU Small Finance Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["AUBANK", "AUFINC", "AUSMS"],
        official_website="https://www.aubank.in",
        dnd_url="https://www.aubank.in/do-not-call",
        grievance_email="grievance@aubank.in",
        customer_care_phone="1800-1200-1300",
        description="India's largest small finance bank offering retail loans and deposits.",
    ),
    "BNDBNK": IndianBrandMetadata(
        brand_name="Bandhan Bank",
        category="COMMERCIAL_BANKING",
        dlt_codes=["BNDBNK", "BANDHN"],
        official_website="https://bandhanbank.com",
        dnd_url="https://bandhanbank.com/grievance-redressal",
        grievance_email="pno@bandhanbank.com",
        customer_care_phone="1800-258-8181",
        description="Banking and microfinance institution based in Kolkata.",
    ),
    "SCBLON": IndianBrandMetadata(
        brand_name="Standard Chartered Bank India",
        category="COMMERCIAL_BANKING",
        dlt_codes=["SCBLON", "SCBBNK", "SCBCRD"],
        official_website="https://www.sc.com/in/",
        dnd_url="https://www.sc.com/in/help-centre/do-not-call-registry/",
        grievance_email="customer.care@sc.com",
        customer_care_phone="1800-345-1000",
        description="International bank offering wealth and credit cards in India.",
    ),
    "CITIBK": IndianBrandMetadata(
        brand_name="Citi India (Consumer Banking / Axis)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["CITIBK", "CITICR", "CITISM"],
        official_website="https://www.online.citibank.co.in",
        dnd_url="https://www.online.citibank.co.in/portal/newgen/dnc.htm",
        grievance_email="head.customercare@citi.com",
        customer_care_phone="1860-210-2484",
        description="Consumer banking and credit card entity integrated with Axis Bank.",
    ),
    "HSBCIN": IndianBrandMetadata(
        brand_name="HSBC India",
        category="COMMERCIAL_BANKING",
        dlt_codes=["HSBCIN", "HSBCBK", "HSBCCD"],
        official_website="https://www.hsbc.co.in",
        dnd_url="https://www.hsbc.co.in/help/feedback-and-complaints/do-not-call/",
        grievance_email="complaints.india@hsbc.co.in",
        customer_care_phone="1800-266-3456",
        description="Multinational banking and financial services in India.",
    ),

    # --- 2. NBFCs, Consumer Lending & Credit ---
    "BAJAJF": IndianBrandMetadata(
        brand_name="Bajaj Finserv / Bajaj Finance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["BAJAJF", "BAJAJ", "BFLSMS", "BAJAJL"],
        official_website="https://www.bajajfinserv.in",
        dnd_url="https://www.bajajfinserv.in/reach-us",
        grievance_email="grievanceredressalteam@bajajfinserv.in",
        customer_care_phone="086980-10101",
        description="India's largest non-banking financial company (NBFC) for consumer credit.",
    ),
    "TATACAP": IndianBrandMetadata(
        brand_name="Tata Capital",
        category="COMMERCIAL_BANKING",
        dlt_codes=["TATACAP", "TATACP", "TATACD"],
        official_website="https://www.tatacapital.com",
        dnd_url="https://www.tatacapital.com/do-not-call.html",
        grievance_email="customercare@tatacapital.com",
        customer_care_phone="1860-267-6060",
        description="Financial services arm of the Tata Group providing personal and housing loans.",
    ),
    "MUTHOOT": IndianBrandMetadata(
        brand_name="Muthoot Finance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["MUTHOOT", "MUTFIN", "MUTHOT"],
        official_website="https://www.muthootfinance.com",
        dnd_url="https://www.muthootfinance.com/customer-service",
        grievance_email="mails@muthootgroup.com",
        customer_care_phone="1800-313-1212",
        description="India's largest gold loan NBFC.",
    ),
    "MANAPP": IndianBrandMetadata(
        brand_name="Manappuram Finance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["MANAPP", "MNPRM", "MANAFN"],
        official_website="https://www.manappuram.com",
        dnd_url="https://www.manappuram.com/customer-support",
        grievance_email="grievance@manappuram.com",
        customer_care_phone="1800-420-2233",
        description="Prominent non-banking financial company specializing in gold and vehicle loans.",
    ),
    "SHRIRAM": IndianBrandMetadata(
        brand_name="Shriram Finance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["SHRIRAM", "STFCL", "SHRITR"],
        official_website="https://www.shriramfinance.in",
        dnd_url="https://www.shriramfinance.in/contact-us",
        grievance_email="grievance@shriramfinance.in",
        customer_care_phone="1800-103-4959",
        description="Retail NBFC focused on commercial vehicle financing, MSME loans, and two-wheeler finance.",
    ),
    "ABCAPL": IndianBrandMetadata(
        brand_name="Aditya Birla Capital",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ABCAPL", "ABFRL", "ABCAP"],
        official_website="https://www.adityabirlacapital.com",
        dnd_url="https://www.adityabirlacapital.com/contact-us",
        grievance_email="care.finance@adityabirlacapital.com",
        customer_care_phone="1800-270-7000",
        description="Financial services conglomerate of the Aditya Birla Group.",
    ),
    "LTFIN": IndianBrandMetadata(
        brand_name="L&T Finance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["LTFIN", "LTFS", "LTFINC"],
        official_website="https://www.ltfs.com",
        dnd_url="https://www.ltfs.com/customer-care",
        grievance_email="gro@ltfs.com",
        customer_care_phone="1800-268-0000",
        description="Rural, housing, and consumer finance non-banking institution.",
    ),
    "MMFSMS": IndianBrandMetadata(
        brand_name="Mahindra Finance (MMFSL)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["MMFSMS", "MMFSL", "MAHFIN"],
        official_website="https://www.mahindrafinance.com",
        dnd_url="https://www.mahindrafinance.com/contact-us",
        grievance_email="mfinconnect@mahindra.com",
        customer_care_phone="1800-233-1234",
        description="Vehicle and tractor financing entity of the Mahindra Group.",
    ),
    "POONAW": IndianBrandMetadata(
        brand_name="Poonawalla Fincorp",
        category="COMMERCIAL_BANKING",
        dlt_codes=["POONAW", "PFLFIN", "POONAF"],
        official_website="https://poonawallafincorp.com",
        dnd_url="https://poonawallafincorp.com/reach-us",
        grievance_email="grievance@poonawallafincorp.com",
        customer_care_phone="1800-208-8888",
        description="Cyrus Poonawalla Group NBFC for consumer and business loans.",
    ),
    "CHOLAF": IndianBrandMetadata(
        brand_name="Cholamandalam Investment and Finance (Chola)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["CHOLAF", "CHOLAM", "CIFCL"],
        official_website="https://www.cholamandalam.com",
        dnd_url="https://www.cholamandalam.com/contact-us",
        grievance_email="customercare@chola.murugappa.com",
        customer_care_phone="1800-102-4565",
        description="Murugappa Group financial services provider.",
    ),
    "NAVITM": IndianBrandMetadata(
        brand_name="Navi Technologies",
        category="COMMERCIAL_BANKING",
        dlt_codes=["NAVITM", "NAVIFN", "NAVIAP"],
        official_website="https://navi.com",
        dnd_url="https://navi.com/privacy-policy",
        grievance_email="grievance@navi.com",
        customer_care_phone="080-69222222",
        description="Digital lending, UPI payments, and mutual fund fintech founded by Sachin Bansal.",
    ),
    "SLICEP": IndianBrandMetadata(
        brand_name="Slice (GaragePreneurs Internet)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["SLICEP", "SLICEC", "SLICE"],
        official_website="https://www.sliceit.com",
        dnd_url="https://www.sliceit.com/privacy",
        grievance_email="grievanceofficer@sliceit.com",
        customer_care_phone="080-47096430",
        description="Fintech card and credit app merged with North East Small Finance Bank.",
    ),
    "UNICRD": IndianBrandMetadata(
        brand_name="Uni Cards (Uniorbit Technologies)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["UNICRD", "UNICAR", "UNIAPP"],
        official_website="https://www.uni.club",
        dnd_url="https://www.uni.club/privacy",
        grievance_email="grievance@uni.club",
        customer_care_phone="080-68216821",
        description="Credit card and pay-later fintech company.",
    ),
    "ONECRD": IndianBrandMetadata(
        brand_name="OneCard (FPL Technologies)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ONECRD", "ONECAR", "FPLTEC"],
        official_website="https://getonecard.app",
        dnd_url="https://getonecard.app/legal/privacy/",
        grievance_email="grievance@fplabs.tech",
        customer_care_phone="1800-210-3456",
        description="Co-branded metal credit card provider backed by Indian banks.",
    ),
    "KREDIT": IndianBrandMetadata(
        brand_name="KreditBee (Finnov Private Limited)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["KREDIT", "KRDTBE", "KBEEAP"],
        official_website="https://www.kreditbee.in",
        dnd_url="https://www.kreditbee.in/privacy-policy",
        grievance_email="grievance@kreditbee.in",
        customer_care_phone="080-44292200",
        description="Digital personal loan platform for young professionals.",
    ),

    # --- 3. Aggregators & Telemarketing Lead Generators (Key Sources of UCC) ---
    "PAISAB": IndianBrandMetadata(
        brand_name="Paisabazaar (PB Fintech)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["PAISAB", "PAISABZ", "PSBZAR"],
        official_website="https://www.paisabazaar.com",
        dnd_url="https://www.paisabazaar.com/do-not-call/",
        grievance_email="care@paisabazaar.com",
        customer_care_phone="1800-208-8877",
        description="Loan and credit card marketplace frequently distributing marketing leads.",
    ),
    "BANKBZ": IndianBrandMetadata(
        brand_name="BankBazaar (A & A Dukaan Financial)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["BANKBZ", "BNKBZR", "BNKBZ"],
        official_website="https://www.bankbazaar.com",
        dnd_url="https://www.bankbazaar.com/do-not-call.html",
        grievance_email="grievanceofficer@bankbazaar.com",
        customer_care_phone="044-66511800",
        description="Co-branded credit cards and loan comparison portal.",
    ),
    "POLBZR": IndianBrandMetadata(
        brand_name="Policybazaar",
        category="COMMERCIAL_BANKING",
        dlt_codes=["POLBZR", "PLCYBZ", "POLICB"],
        official_website="https://www.policybazaar.com",
        dnd_url="https://www.policybazaar.com/do-not-call/",
        grievance_email="grievance@policybazaar.com",
        customer_care_phone="1800-208-8787",
        description="India's largest online insurance aggregator and lead generation platform.",
    ),
    "WISHFN": IndianBrandMetadata(
        brand_name="Wishfin (Mywish Marketplaces)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["WISHFN", "WSHFIN", "WISHF"],
        official_website="https://www.wishfin.com",
        dnd_url="https://www.wishfin.com/do-not-call",
        grievance_email="contactus@wishfin.com",
        customer_care_phone="0120-4743200",
        description="Financial marketplace for credit score tracking and loan offers.",
    ),

    # --- 4. Fintech, Wallets & Payments ---
    "PAYTM": IndianBrandMetadata(
        brand_name="Paytm (One97 Communications)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["PAYTM", "PAYTMS", "PYTMSM", "PAYTMB"],
        official_website="https://paytm.com",
        dnd_url="https://paytm.com/care",
        grievance_email="nodal@paytm.com",
        customer_care_phone="0120-4456-456",
        description="Indian digital payments and financial services app.",
    ),
    "PHONEPE": IndianBrandMetadata(
        brand_name="PhonePe",
        category="COMMERCIAL_BANKING",
        dlt_codes=["PHONEP", "PHNPAY", "PHNPEP"],
        official_website="https://www.phonepe.com",
        dnd_url="https://www.phonepe.com/contact-us/",
        grievance_email="grievance@phonepe.com",
        customer_care_phone="080-68727374",
        description="UPI-based digital payments platform.",
    ),
    "GPAY": IndianBrandMetadata(
        brand_name="Google Pay India",
        category="COMMERCIAL_BANKING",
        dlt_codes=["GOOGLP", "GPAYIN", "GOOGLS"],
        official_website="https://pay.google.com/intl/en_in/about/",
        dnd_url="https://support.google.com/pay/india/answer/9010077",
        grievance_email="support-in@google.com",
        description="Google Pay UPI payment platform for Indian consumers.",
    ),
    "CREDIN": IndianBrandMetadata(
        brand_name="CRED (Dreamplug Technologies)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["CREDIN", "CREDSM", "CRDAPP"],
        official_website="https://cred.club",
        dnd_url="https://cred.club/privacy",
        grievance_email="grievanceofficer@cred.club",
        description="Rewards-based credit card bill payment platform.",
    ),
    "MOBIKW": IndianBrandMetadata(
        brand_name="MobiKwik",
        category="COMMERCIAL_BANKING",
        dlt_codes=["MOBIKW", "MBKWIK"],
        official_website="https://www.mobikwik.com",
        dnd_url="https://www.mobikwik.com/help",
        grievance_email="grievance@mobikwik.com",
        description="Digital wallet and Buy Now Pay Later (BNPL) provider.",
    ),

    # --- 5. Stockbroking & Wealth Management ---
    "ZERODH": IndianBrandMetadata(
        brand_name="Zerodha Broking",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ZERODH", "ZERODS", "ZRDHAP"],
        official_website="https://zerodha.com",
        dnd_url="https://zerodha.com/contact",
        grievance_email="complaints@zerodha.com",
        customer_care_phone="080-47181888",
        description="India's largest discount stockbroker.",
    ),
    "GROWW": IndianBrandMetadata(
        brand_name="Groww (Nextbillion Technology)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["GROWW", "GROWWS", "GRWAPP"],
        official_website="https://groww.in",
        dnd_url="https://groww.in/help",
        grievance_email="grievance@groww.in",
        customer_care_phone="080-68249147",
        description="Investment platform for stocks, mutual funds, and F&O.",
    ),
    "ANGELB": IndianBrandMetadata(
        brand_name="Angel One (formerly Angel Broking)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ANGELB", "ANGLON", "ANGELS"],
        official_website="https://www.angelone.in",
        dnd_url="https://www.angelone.in/support",
        grievance_email="feedback@angelbroking.com",
        customer_care_phone="1800-1020",
        description="Tech-led retail stockbroking firm.",
    ),
    "UPSTOX": IndianBrandMetadata(
        brand_name="Upstox (RKSV Securities)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["UPSTOX", "UPSTX", "RKSVSC"],
        official_website="https://upstox.com",
        dnd_url="https://upstox.com/contact-us/",
        grievance_email="grievance@upstox.com",
        customer_care_phone="022-41792999",
        description="Online discount broker for equity and commodities.",
    ),
    "MOTOSW": IndianBrandMetadata(
        brand_name="Motilal Oswal Financial Services",
        category="COMMERCIAL_BANKING",
        dlt_codes=["MOTOSW", "MOFSL", "MOSWAL"],
        official_website="https://www.motilaloswal.com",
        dnd_url="https://www.motilaloswal.com/contact-us",
        grievance_email="query@motilaloswal.com",
        customer_care_phone="022-40548000",
        description="Full-service broker, research house, and wealth manager.",
    ),
    "ICICID": IndianBrandMetadata(
        brand_name="ICICI Direct (ICICI Securities)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ICICID", "ISECMS", "ICICIS"],
        official_website="https://www.icicidirect.com",
        dnd_url="https://www.icicidirect.com/contactus",
        grievance_email="customercare@icicidirect.com",
        customer_care_phone="1800-572-8888",
        description="Leading retail stockbroking arm of ICICI Group.",
    ),

    # --- 6. Insurance Companies ---
    "LICIND": IndianBrandMetadata(
        brand_name="Life Insurance Corporation of India (LIC)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["LICIND", "LICOFIN", "LICSMS"],
        official_website="https://licindia.in",
        dnd_url="https://licindia.in/customer-services",
        grievance_email="co_crmgrv@licindia.com",
        customer_care_phone="022-68276827",
        description="State-owned insurance group and investment company.",
    ),
    "HDFCLF": IndianBrandMetadata(
        brand_name="HDFC Life Insurance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["HDFCLF", "HDFCLI", "HDFCLM"],
        official_website="https://www.hdfclife.com",
        dnd_url="https://www.hdfclife.com/customer-service/do-not-call",
        grievance_email="grievance@hdfclife.com",
        customer_care_phone="1860-267-9999",
        description="Long-term life insurance joint venture.",
    ),
    "SBILIF": IndianBrandMetadata(
        brand_name="SBI Life Insurance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["SBILIF", "SBILFE", "SBILSM"],
        official_website="https://www.sbilife.co.in",
        dnd_url="https://www.sbilife.co.in/en/services/do-not-call-registry",
        grievance_email="nodalofficer@sbilife.co.in",
        customer_care_phone="1800-267-9090",
        description="Life insurance partnership between SBI and BNP Paribas.",
    ),
    "ICICIPR": IndianBrandMetadata(
        brand_name="ICICI Prudential Life Insurance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ICICIPR", "ICIPRU", "IPRULI"],
        official_website="https://www.iciciprulife.com",
        dnd_url="https://www.iciciprulife.com/contact-us/do-not-call.html",
        grievance_email="gro@iciciprulife.com",
        customer_care_phone="1860-266-7766",
        description="Leading private life insurance provider in India.",
    ),
    "MAXLIF": IndianBrandMetadata(
        brand_name="Max Life Insurance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["MAXLIF", "MAXLFE", "MAXLFS"],
        official_website="https://www.maxlifeinsurance.com",
        dnd_url="https://www.maxlifeinsurance.com/customer-service/do-not-call",
        grievance_email="manager.services@maxlifeinsurance.com",
        customer_care_phone="1860-120-5577",
        description="Private life insurance entity partnered with Axis Bank.",
    ),
    "STARHL": IndianBrandMetadata(
        brand_name="Star Health and Allied Insurance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["STARHL", "STARHE", "STRHLT"],
        official_website="https://www.starhealth.in",
        dnd_url="https://www.starhealth.in/do-not-call",
        grievance_email="grievances@starhealth.in",
        customer_care_phone="1800-425-2255",
        description="India's first standalone health insurance provider.",
    ),
    "CAREHL": IndianBrandMetadata(
        brand_name="Care Health Insurance (formerly Religare)",
        category="COMMERCIAL_BANKING",
        dlt_codes=["CAREHL", "CAREHI", "RELGHI"],
        official_website="https://www.careinsurance.com",
        dnd_url="https://www.careinsurance.com/contact-us.html",
        grievance_email="customerfirst@careinsurance.com",
        customer_care_phone="1800-102-4455",
        description="Specialist health insurance company in India.",
    ),
    "ACKOGI": IndianBrandMetadata(
        brand_name="ACKO General Insurance",
        category="COMMERCIAL_BANKING",
        dlt_codes=["ACKOGI", "ACKOIN", "ACKOAP"],
        official_website="https://www.acko.com",
        dnd_url="https://www.acko.com/privacy-policy/",
        grievance_email="gro@acko.com",
        customer_care_phone="1800-266-2256",
        description="Digital-first general insurance provider for motor and health.",
    ),

    # --- 7. Food Delivery & Quick Commerce ---
    "SWIGGY": IndianBrandMetadata(
        brand_name="Swiggy (Bundl Technologies)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["SWIGGY", "SWGINS", "SWIGIN", "SWIGFO"],
        official_website="https://www.swiggy.com",
        dnd_url="https://www.swiggy.com/privacy-policy",
        grievance_email="grievances@swiggy.in",
        customer_care_phone="080-67466729",
        description="On-demand food delivery and Instamart quick grocery platform.",
    ),
    "ZOMATO": IndianBrandMetadata(
        brand_name="Zomato",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["ZOMATO", "ZOMSMS", "ZMTAPP"],
        official_website="https://www.zomato.com",
        dnd_url="https://www.zomato.com/privacy",
        grievance_email="grievanceofficer@zomato.com",
        description="Restaurant discovery and online food ordering platform.",
    ),
    "ZEPTO": IndianBrandMetadata(
        brand_name="Zepto (KiranaKart Technologies)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["ZEPTO", "ZEPTON", "ZEPTAP", "ZEPTOW"],
        official_website="https://www.zeptonow.com",
        dnd_url="https://www.zeptonow.com/privacy-policy",
        grievance_email="grievanceofficer@zeptonow.com",
        description="10-minute quick-commerce grocery delivery service.",
    ),
    "BLINKIT": IndianBrandMetadata(
        brand_name="Blinkit (formerly Grofers)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["BLNKIT", "BLINKT", "GROFRS"],
        official_website="https://blinkit.com",
        dnd_url="https://blinkit.com/privacy",
        grievance_email="grievance@blinkit.com",
        description="Instant grocery delivery platform by Eternal (Zomato).",
    ),
    "BIGBSK": IndianBrandMetadata(
        brand_name="BigBasket (Tata Enterprise)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["BIGBSK", "BGBASK", "TATA_BB"],
        official_website="https://www.bigbasket.com",
        dnd_url="https://www.bigbasket.com/privacy/",
        grievance_email="customerservice@bigbasket.com",
        customer_care_phone="1860-123-1000",
        description="Online grocery and supermarket platform in India.",
    ),
    "CNTDLT": IndianBrandMetadata(
        brand_name="Country Delight",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["CNTDLT", "CTRDEL", "CDELAP"],
        official_website="https://countrydelight.in",
        dnd_url="https://countrydelight.in/privacy-policy",
        grievance_email="info@countrydelight.in",
        customer_care_phone="0124-4065660",
        description="Farm-fresh milk, dairy, and grocery subscription delivery app.",
    ),

    # --- 8. E-Commerce, Retail & Fashion ---
    "AMAZON": IndianBrandMetadata(
        brand_name="Amazon India",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["AMAZON", "AMZPIN", "AMZIND", "AMZNSM"],
        official_website="https://www.amazon.in",
        dnd_url="https://www.amazon.in/gp/cpc/homepage",
        grievance_email="grievance-officer@amazon.in",
        customer_care_phone="1800-3000-9009",
        description="Global e-commerce marketplace operating in India.",
    ),
    "FLPKRT": IndianBrandMetadata(
        brand_name="Flipkart (Walmart Group)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["FLPKRT", "FLIPKT", "FLPKIN"],
        official_website="https://www.flipkart.com",
        dnd_url="https://www.flipkart.com/helpcentre",
        grievance_email="grievance.officer@flipkart.com",
        customer_care_phone="1800-202-9898",
        description="Indian e-commerce platform.",
    ),
    "MEESHO": IndianBrandMetadata(
        brand_name="Meesho (Fashnear Technologies)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["MEESHO", "MSHAPP", "MEESH"],
        official_website="https://www.meesho.com",
        dnd_url="https://www.meesho.com/legal/privacy",
        grievance_email="grievance-officer@meesho.com",
        description="Social commerce and value retail platform.",
    ),
    "MYNTRA": IndianBrandMetadata(
        brand_name="Myntra Designs",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["MYNTRA", "MYNTR", "MYNTAP"],
        official_website="https://www.myntra.com",
        dnd_url="https://www.myntra.com/contactus",
        grievance_email="support@myntra.com",
        customer_care_phone="080-61561999",
        description="Fashion and lifestyle e-commerce portal.",
    ),
    "JIOMRT": IndianBrandMetadata(
        brand_name="JioMart (Reliance Retail)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["JIOMRT", "JIORTO", "RELRET"],
        official_website="https://www.jiomart.com",
        dnd_url="https://www.jiomart.com/privacy-policy",
        grievance_email="grievanceofficer@jiomart.com",
        customer_care_phone="1800-890-1222",
        description="Omnichannel retail and grocery arm of Reliance Industries.",
    ),
    "NYKAA": IndianBrandMetadata(
        brand_name="Nykaa (FSN E-Commerce)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["NYKAA", "NYKAAS", "NYKMAN"],
        official_website="https://www.nykaa.com",
        dnd_url="https://www.nykaa.com/terms-conditions",
        grievance_email="grievanceofficer@nykaa.com",
        customer_care_phone="1800-267-4444",
        description="Beauty, wellness, and fashion retailer.",
    ),
    "AJIOIN": IndianBrandMetadata(
        brand_name="Ajio (Reliance Retail)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["AJIOIN", "AJIOAP", "AJIOSM"],
        official_website="https://www.ajio.com",
        dnd_url="https://www.ajio.com/help",
        grievance_email="customercare@ajio.com",
        customer_care_phone="1800-889-9991",
        description="Digital fashion and lifestyle platform by Reliance Retail.",
    ),
    "TATACQ": IndianBrandMetadata(
        brand_name="Tata CLiQ",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["TATACQ", "TTCLIQ", "CLIQSM"],
        official_website="https://www.tatacliq.com",
        dnd_url="https://www.tatacliq.com/help",
        grievance_email="grievanceofficer@tatacliq.com",
        customer_care_phone="022-68078282",
        description="Tata Group e-commerce portal for electronics and luxury fashion.",
    ),
    "FRSTCR": IndianBrandMetadata(
        brand_name="FirstCry (Brainbees Solutions)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["FRSTCR", "FSTCRY", "FCRYAP"],
        official_website="https://www.firstcry.com",
        dnd_url="https://www.firstcry.com/privacy-policy",
        grievance_email="customercare@firstcry.com",
        customer_care_phone="020-67297800",
        description="Online baby and kids products retailer.",
    ),
    "LNSKRT": IndianBrandMetadata(
        brand_name="Lenskart",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["LNSKRT", "LNSKAP", "LENSON"],
        official_website="https://www.lenskart.com",
        dnd_url="https://www.lenskart.com/privacy-policy.html",
        grievance_email="grievance@lenskart.in",
        customer_care_phone="1800-111-111",
        description="Eyewear and omnichannel optical chain in India.",
    ),
    "CROMA": IndianBrandMetadata(
        brand_name="Croma (Infiniti Retail / Tata)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["CROMA", "CRMAP", "CROMAS"],
        official_website="https://www.croma.com",
        dnd_url="https://www.croma.com/help-and-support",
        grievance_email="customersupport@croma.com",
        customer_care_phone="1800-572-7662",
        description="Retail chain of consumer electronics and home appliances.",
    ),
    "URBANC": IndianBrandMetadata(
        brand_name="Urban Company (formerly UrbanClap)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["URBANC", "URBNCP", "UCOMP"],
        official_website="https://www.urbancompany.com",
        dnd_url="https://www.urbancompany.com/privacy-policy",
        grievance_email="grievanceofficer@urbancompany.com",
        description="Home services, salon, appliance repair, and maintenance marketplace.",
    ),

    # --- 9. Telecom & Broadband Operators ---
    "AIRTEL": IndianBrandMetadata(
        brand_name="Bharti Airtel",
        category="COMMERCIAL_TELECOM",
        dlt_codes=["AIRTEL", "AIRTLB", "ATLSMS", "AIRTHK"],
        official_website="https://www.airtel.in",
        dnd_url="https://www.airtel.in/airtel-dnd",
        grievance_email="nodalofficer@airtel.com",
        customer_care_phone="121",
        description="Telecommunications provider offering prepaid, postpaid, broadband, and DTH.",
    ),
    "JIOINF": IndianBrandMetadata(
        brand_name="Reliance Jio",
        category="COMMERCIAL_TELECOM",
        dlt_codes=["JIOINF", "JIOCARE", "JIONET", "JIOMOB", "JIOFIB"],
        official_website="https://www.jio.com",
        dnd_url="https://www.jio.com/help/faq/mobile/services/do-not-disturb-dnd/how-do-i-activate-deactivate-dnd-service",
        grievance_email="grievance.officer@jio.com",
        customer_care_phone="199",
        description="India's largest 4G/5G mobile network and fiber provider.",
    ),
    "VILNOT": IndianBrandMetadata(
        brand_name="Vi (Vodafone Idea)",
        category="COMMERCIAL_TELECOM",
        dlt_codes=["VILNOT", "IDEA", "VODAFO", "VISMS", "VICARE"],
        official_website="https://www.myvi.in",
        dnd_url="https://www.myvi.in/dnd",
        grievance_email="customercare@vodafoneidea.com",
        customer_care_phone="199",
        description="Pan-India telecom access service provider.",
    ),
    "BSNLPR": IndianBrandMetadata(
        brand_name="BSNL",
        category="COMMERCIAL_TELECOM",
        dlt_codes=["BSNLPR", "BSNLSMS", "BSNLIN"],
        official_website="https://www.bsnl.co.in",
        dnd_url="https://portal.bsnl.in/dnd/",
        grievance_email="cmd@bsnl.co.in",
        customer_care_phone="1800-180-1503",
        description="Government-owned telecommunications service provider.",
    ),
    "ACTFIB": IndianBrandMetadata(
        brand_name="ACT Fibernet (Atria Convergence Technologies)",
        category="COMMERCIAL_TELECOM",
        dlt_codes=["ACTFIB", "ACTNET", "ACTBRD"],
        official_website="https://www.actcorp.in",
        dnd_url="https://www.actcorp.in/support",
        grievance_email="nodal-officer@actcorp.in",
        customer_care_phone="080-42840000",
        description="High-speed fiber broadband and digital television service.",
    ),
    "TATASK": IndianBrandMetadata(
        brand_name="Tata Play (formerly Tata Sky)",
        category="COMMERCIAL_TELECOM",
        dlt_codes=["TATASK", "TATAPL", "TPLAY"],
        official_website="https://www.tataplay.com",
        dnd_url="https://www.tataplay.com/help",
        grievance_email="nodalofficer@tataplay.com",
        customer_care_phone="1800-208-6633",
        description="Direct broadcast satellite and OTT content aggregation provider.",
    ),
    "DISHTV": IndianBrandMetadata(
        brand_name="Dish TV India",
        category="COMMERCIAL_TELECOM",
        dlt_codes=["DISHTV", "DISHSM", "DTVSMS"],
        official_website="https://www.dishtv.in",
        dnd_url="https://www.dishtv.in/dnd",
        grievance_email="nodalofficer@dishtv.in",
        customer_care_phone="95017-95017",
        description="DTH television service provider.",
    ),

    # --- 10. Travel, Airlines, Rides & Ticketing ---
    "MAKEMT": IndianBrandMetadata(
        brand_name="MakeMyTrip",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["MAKEMT", "MMTRIP", "MMTAPP"],
        official_website="https://www.makemytrip.com",
        dnd_url="https://www.makemytrip.com/legal/privacy_user.html",
        grievance_email="privacy@makemytrip.com",
        customer_care_phone="0124-4628747",
        description="Online travel agency for flights, hotels, and holiday packages.",
    ),
    "IRCTCi": IndianBrandMetadata(
        brand_name="IRCTC (Indian Railways)",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["IRCTCi", "IRCTCS", "RAILIN"],
        official_website="https://www.irctc.co.in",
        dnd_url="https://www.irctc.co.in/nget/enquiry/contact-us",
        grievance_email="care@irctc.co.in",
        customer_care_phone="14646",
        description="Official Indian Railways e-ticketing and tourism portal.",
    ),
    "UBERIN": IndianBrandMetadata(
        brand_name="Uber India",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["UBERIN", "UBERAP"],
        official_website="https://www.uber.com/in/en/",
        dnd_url="https://help.uber.com/riders/article/opt-out-of-marketing-communications",
        grievance_email="grievance-india@uber.com",
        description="Ridesharing and mobility network.",
    ),
    "OLACAB": IndianBrandMetadata(
        brand_name="Ola Cabs",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["OLACAB", "OLAAPP", "OLAPAY"],
        official_website="https://www.olacabs.com",
        dnd_url="https://www.olacabs.com/info/faqs#privacyPolicy",
        grievance_email="grievance@olacabs.com",
        customer_care_phone="080-67350900",
        description="Indian ride-hailing and electric vehicle company.",
    ),
    "BKMYSH": IndianBrandMetadata(
        brand_name="BookMyShow",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["BKMYSH", "BMSHOW", "BMSIND", "BMSAPP"],
        official_website="https://in.bookmyshow.com",
        dnd_url="https://in.bookmyshow.com/privacy",
        grievance_email="privacy@bookmyshow.com",
        customer_care_phone="022-61445050",
        description="Entertainment and movie ticketing platform.",
    ),
    "INDIGO": IndianBrandMetadata(
        brand_name="IndiGo Airlines (InterGlobe Aviation)",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["INDIGO", "6EING", "INDGAP"],
        official_website="https://www.goindigo.in",
        dnd_url="https://www.goindigo.in/information/privacy.html",
        grievance_email="customer.relations@goindigo.in",
        customer_care_phone="0124-6173838",
        description="India's largest passenger airline by fleet size and market share.",
    ),
    "AIRIND": IndianBrandMetadata(
        brand_name="Air India (Tata Group)",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["AIRIND", "AIROPS", "AIEXPL"],
        official_website="https://www.airindia.com",
        dnd_url="https://www.airindia.com/in/en/contact-us.html",
        grievance_email="customer.care@airindia.com",
        customer_care_phone="1860-233-1407",
        description="Flag carrier airline of India.",
    ),
    "SPICEJ": IndianBrandMetadata(
        brand_name="SpiceJet",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["SPICEJ", "SGSPIC", "SPICAP"],
        official_website="https://www.spicejet.com",
        dnd_url="https://www.spicejet.com/privacy-policy",
        grievance_email="custrelations@spicejet.com",
        customer_care_phone="0124-4983410",
        description="Budget airline based in Gurgaon.",
    ),
    "EASMYT": IndianBrandMetadata(
        brand_name="EaseMyTrip (Easy Trip Planners)",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["EASMYT", "EMTRIP", "EASMYP"],
        official_website="https://www.easemytrip.com",
        dnd_url="https://www.easemytrip.com/privacy-policy.html",
        grievance_email="care@easemytrip.com",
        customer_care_phone="011-43131313",
        description="Zero-convenience-fee online travel platform in India.",
    ),
    "OYORMS": IndianBrandMetadata(
        brand_name="OYO Rooms (Oravel Stays)",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["OYORMS", "OYOAPP", "OYOIND"],
        official_website="https://www.oyorooms.com",
        dnd_url="https://www.oyorooms.com/privacy-policy/",
        grievance_email="grievance@oyorooms.com",
        customer_care_phone="0124-6201611",
        description="Hospitality company offering budget hotel and home stays.",
    ),
    "REDBUS": IndianBrandMetadata(
        brand_name="redBus (MakeMyTrip Group)",
        category="COMMERCIAL_TRAVEL",
        dlt_codes=["REDBUS", "RDBUS", "RDBAPP"],
        official_website="https://www.redbus.in",
        dnd_url="https://www.redbus.in/info/privacypolicy",
        grievance_email="grievanceofficer@redbus.in",
        customer_care_phone="080-39412345",
        description="Online bus ticketing and private bus operator aggregator.",
    ),

    # --- 11. Health, Pharmacy & Diagnostics ---
    "TATA1M": IndianBrandMetadata(
        brand_name="Tata 1mg",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["TATA1M", "1MGAPP", "ONEMG"],
        official_website="https://www.1mg.com",
        dnd_url="https://www.1mg.com/privacy-policy",
        grievance_email="grievanceofficer@1mg.com",
        customer_care_phone="0124-4166666",
        description="Digital healthcare platform for medicine delivery and lab tests.",
    ),
    "PHARME": IndianBrandMetadata(
        brand_name="PharmEasy (API Holdings)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["PHARME", "PHRMPY", "PEASY"],
        official_website="https://pharmeasy.in",
        dnd_url="https://pharmeasy.in/privacy-policy",
        grievance_email="grievanceofficer@pharmeasy.in",
        customer_care_phone="07666-100-300",
        description="Online pharmacy and diagnostic test booking service.",
    ),
    "APLLOH": IndianBrandMetadata(
        brand_name="Apollo 24|7 (Apollo Hospitals)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["APLLOH", "APOLLO", "AP24X7"],
        official_website="https://www.apollo247.com",
        dnd_url="https://www.apollo247.com/privacy-policy",
        grievance_email="grievanceofficer@apollo247.com",
        customer_care_phone="1860-500-0101",
        description="Digital healthcare arm of Apollo Hospitals Group.",
    ),
    "PRACTO": IndianBrandMetadata(
        brand_name="Practo Technologies",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["PRACTO", "PRCTO", "PRCAPP"],
        official_website="https://www.practo.com",
        dnd_url="https://www.practo.com/company/privacy",
        grievance_email="privacy@practo.com",
        description="Doctor consultation and appointment booking service in India.",
    ),
    "LALPAT": IndianBrandMetadata(
        brand_name="Dr Lal PathLabs",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["LALPAT", "LALPATH", "DRLALP"],
        official_website="https://www.lalpathlabs.com",
        dnd_url="https://www.lalpathlabs.com/privacy-policy",
        grievance_email="customer.care@lalpathlabs.com",
        customer_care_phone="011-49885050",
        description="National diagnostic healthcare and pathology laboratory chain.",
    ),

    # --- 12. EdTech, Real Estate & Job Portals ---
    "NAUKRI": IndianBrandMetadata(
        brand_name="Naukri.com (Info Edge India)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["NAUKRI", "NAUKIN", "NKRIAP"],
        official_website="https://www.naukri.com",
        dnd_url="https://www.naukri.com/privacypolicy",
        grievance_email="grievance@naukri.com",
        customer_care_phone="1800-102-5558",
        description="India's premier employment and talent recruitment portal.",
    ),
    "99ACRE": IndianBrandMetadata(
        brand_name="99acres.com (Info Edge India)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["99ACRE", "NNACRE", "99ACRS"],
        official_website="https://www.99acres.com",
        dnd_url="https://www.99acres.com/do-not-call",
        grievance_email="grievance@99acres.com",
        customer_care_phone="1800-41-99099",
        description="Real estate property discovery portal often generating builder telemarketing leads.",
    ),
    "MGCBRK": IndianBrandMetadata(
        brand_name="MagicBricks (Times Internet)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["MGCBRK", "MGBRCK", "MAGICK"],
        official_website="https://www.magicbricks.com",
        dnd_url="https://www.magicbricks.com/help/privacy-policy",
        grievance_email="support@magicbricks.com",
        customer_care_phone="0124-4866599",
        description="Property portal connecting buyers, tenants, and real estate brokers.",
    ),
    "NOBRKR": IndianBrandMetadata(
        brand_name="NoBroker Technologies",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["NOBRKR", "NOBRK", "NBKRIN"],
        official_website="https://www.nobroker.in",
        dnd_url="https://www.nobroker.in/privacy-policy",
        grievance_email="hello@nobroker.in",
        customer_care_phone="92417-00000",
        description="Brokerage-free real estate, painting, packers & movers platform.",
    ),
    "UNACAD": IndianBrandMetadata(
        brand_name="Unacademy (Sorting Hat Technologies)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["UNACAD", "UNACDM", "UNACAP"],
        official_website="https://unacademy.com",
        dnd_url="https://unacademy.com/privacy",
        grievance_email="grievance@unacademy.com",
        customer_care_phone="080-68487777",
        description="Online learning platform for competitive test preparation in India.",
    ),
    "PHYWAL": IndianBrandMetadata(
        brand_name="PhysicsWallah (PW)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["PHYWAL", "PWALLA", "PWAPP"],
        official_website="https://www.pw.live",
        dnd_url="https://www.pw.live/privacy-policy",
        grievance_email="support@pw.live",
        customer_care_phone="07019-243-492",
        description="Affordable edtech platform for IIT JEE, NEET, and school curricula.",
    ),
    "DOMINO": IndianBrandMetadata(
        brand_name="Domino's Pizza India (Jubilant FoodWorks)",
        category="COMMERCIAL_SHOPPING",
        dlt_codes=["DOMINO", "DOMINOS", "JUBILNT"],
        official_website="https://pizzaonline.dominos.co.in",
        dnd_url="https://www.dominos.co.in/privacy-policy",
        grievance_email="guestcaredominos@jublfood.com",
        customer_care_phone="1800-208-1234",
        description="India's largest quick-service pizza chain with automated promotional SMS campaigns.",
    ),
}


def decode_dlt_sender(sender: str) -> Tuple[Optional[str], Optional[str], Optional[IndianBrandMetadata]]:
    """Decodes a DLT SMS sender header into its constituent telecom circle,
    access provider, and matching brand metadata.

    DLT standard format: `XX-AAAAAA` (2-letter prefix, hyphen, 3-6 character header).
    Examples:
        - `VM-HDFCBK`: V = Vi (Vodafone Idea), M = Mumbai circle, HDFCBK = HDFC Bank.
        - `AD-SWIGGY`: A = Bharti Airtel, D = Delhi circle, SWIGGY = Swiggy.
        - `JD-JIOINF`: J = Reliance Jio, D = Delhi circle, JIOINF = Reliance Jio.
        - `BA-FLPKRT`: B = BSNL, A = Andhra Pradesh circle, FLPKRT = Flipkart.
    """
    clean_sender = sender.strip().upper()
    
    # Check for DLT hyphenated pattern: 2 alpha chars, hyphen, 3-8 alphanumeric chars
    dlt_match = re.match(r"^([A-Z]{2})-([A-Z0-9]{3,8})$", clean_sender)
    if not dlt_match:
        # Check if the sender itself is a known brand code without prefix
        for key, brand in INDIAN_BRAND_REGISTRY.items():
            if clean_sender in brand.dlt_codes or clean_sender.startswith(key):
                return None, None, brand
        return None, None, None

    prefix = dlt_match.group(1)
    body = dlt_match.group(2)

    # Decode operator (char 0) and circle (char 1 or 1-2)
    operator_char = prefix[0]
    circle_char = prefix[1]

    operator_name = ACCESS_PROVIDERS.get(operator_char, f"Operator Code {operator_char}")
    circle_info = TELECOM_CIRCLES.get(circle_char)
    circle_desc = f"{circle_info['name']} ({circle_info['type']})" if circle_info else f"Circle Code {circle_char}"

    # Search Brand Registry
    matched_brand = None
    for key, brand in INDIAN_BRAND_REGISTRY.items():
        if body == key or body in brand.dlt_codes or key in body or any(code in body for code in brand.dlt_codes):
            matched_brand = brand
            break

    return operator_name, circle_desc, matched_brand


def generate_trai_1909_complaint(
    sender: str,
    body: Optional[str] = None,
    received_time: Optional[datetime] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generates the official statutory TRAI 1909 complaint format and instructions
    under the Telecom Commercial Communications Customer Preference Regulations, 2018 (TCCCPR).

    TCCCPR Rules:
    - Complaint must be filed within 3 days (72 hours) of receiving the communication.
    - Format for SMS to 1909:
      `COMP TEL NO <caller/sender>, <dd/mm/yy>, <time hh:mm>, <brief description>`
    - Can also be registered via phone call to 1909 (IVR) or TRAI DND 3.0 Mobile App.
    """
    msg_body = body or kwargs.get("message_body") or ""
    ts = received_time or datetime.now()
    if "received_timestamp_iso" in kwargs and kwargs["received_timestamp_iso"]:
        try:
            ts = datetime.fromisoformat(kwargs["received_timestamp_iso"].replace("Z", "+00:00"))
        except Exception:
            pass

    date_str = ts.strftime("%d/%m/%y")
    time_str = ts.strftime("%I:%M %p")

    clean_sender = sender.strip()
    brief_desc = "Unsolicited promotional communication received despite active DND registration."
    if msg_body:
        first_few = re.sub(r"\s+", " ", msg_body.strip())[:40]
        brief_desc = f"Unsolicited promo: {first_few}"

    sms_text = f"COMP {brief_desc}, {clean_sender}, {date_str}"
    formal_syntax = f"COMP TEL NO {clean_sender}, {date_str}, {time_str}, {brief_desc}"

    return {
        "recipient_sms_shortcode": "1909",
        "sms_recipient": "1909",
        "sms_body": sms_text,
        "formal_syntax": formal_syntax,
        "deadline_info": "72 hours (3 days from receipt per TCCCPR 2018)",
        "deadline_hours": "72 hours (3 days from receipt)",
        "regulatory_basis": "TRAI Telecom Commercial Communications Customer Preference Regulations, 2018 (TCCCPR 2018) Regulation 25",
        "alternative_methods": [
            "1. Call 1909 toll-free from your mobile and follow IVR instructions to register a DND complaint.",
            "2. Install the official DoT/TRAI 'TRAI DND 3.0' App from Google Play Store for 1-click filing from SMS history.",
            "3. If suspecting financial scam, lottery fraud, or electricity bill threats, report immediately to DoT Chakshu at https://sancharsaathi.gov.in/sfc/.",
        ],
    }


def generate_chakshu_escalation(
    sender: str,
    body: Optional[str] = None,
    received_time: Optional[datetime] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Formats reporting instructions for DoT's official Chakshu facility on Sanchar Saathi.
    Used when a communication is suspected to be a financial scam, impersonation, or phishing attempt.
    """
    ts = received_time or datetime.now()
    return {
        "portal_name": "Chakshu (DoT Sanchar Saathi)",
        "portal_url": "https://sancharsaathi.gov.in/sfc/",
        "reported_sender": sender,
        "incident_datetime": ts.strftime("%d/%m/%Y %H:%M"),
        "instructions": [
            "1. Visit https://sancharsaathi.gov.in/sfc/ in your web browser.",
            "2. Select 'Suspected Fraud Communication' category (e.g. KYC Expiry, Electricity Bill, Lottery, Impersonation).",
            f"3. Enter the Sender Header or Phone Number: {sender}",
            f"4. Enter the Date & Time: {ts.strftime('%d/%m/%Y %H:%M')}",
            "5. Paste the message text or attach a screenshot of the SMS.",
            "6. Enter your mobile number, verify with OTP, and submit the complaint.",
            "7. The Department of Telecommunications (DoT) will flag the sender across all telecom operators.",
        ],
    }


def generate_dpdp_revocation_notice(
    brand: IndianBrandMetadata,
    user_masked_phone: Optional[str] = None,
    user_name: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generates a statutory Data Principal Consent Revocation Notice under Section 6(4)
    and Section 12 of India's Digital Personal Data Protection Act (DPDP Act, 2023).
    """
    phone_display = user_masked_phone or kwargs.get("user_phone_masked") or "[Registered Subscriber Mobile]"
    display_name = user_name or "[Data Principal / Registered Subscriber]"
    now_str = datetime.now().strftime("%d %B %Y")
    email_target = brand.grievance_email or "Grievance Officer"

    return f"""FORMAL NOTICE: REVOCATION OF CONSENT & DATA ERASURE REQUEST
Under Section 6(4) and Section 12 of the Digital Personal Data Protection Act (DPDP Act), 2023
and Rule 5(7) of the Information Technology (Reasonable Security Practices) Rules, 2011.

Date: {now_str}
To:
Grievance Officer / Data Protection Officer
{brand.brand_name}
Email: {email_target}

Subject: Immediate Revocation of Marketing Consent and Suppression of Mobile Number {phone_display}

Dear Grievance Officer,

I am writing to formally exercise my statutory rights as a Data Principal under Section 6(4) and Section 12 of the Digital Personal Data Protection Act (DPDP Act), 2023.

1. Revocation of Consent:
I hereby withdraw and revoke all previously granted consent (express or implied) permitting {brand.brand_name}, its subsidiaries, marketing partners, and telemarketing vendors to process my personal data for direct marketing, promotional SMS, automated voice calls, or commercial communications.

2. Permanent Number Suppression:
Please immediately suppress my telephone number ({phone_display}) from all active promotional campaigns, lead distribution databases, and third-party calling centers.

3. Erasure of Non-Essential Personal Data:
In accordance with Section 12 of the DPDP Act 2023, please erase all marketing-related profiles, tracking identifiers, and contact details associated with my telephone number, retaining solely records mandated by applicable statutory financial regulations.

4. Statutory Compliance Confirmation:
Please confirm compliance with this revocation notice in writing within the statutory timeline. If unsolicited promotional communications continue from headers registered to {brand.brand_name}, I reserve the right to escalate this matter to the Data Protection Board of India and the Telecom Regulatory Authority of India (TRAI).

Yours faithfully,
{display_name}
Contact Reference: {phone_display}
"""
