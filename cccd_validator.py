import re

PROVINCES = {
    "001": "Hà Nội", "002": "Hà Giang", "004": "Cao Bằng", "006": "Bắc Kạn",
    "008": "Tuyên Quang", "010": "Lào Cai", "011": "Điện Biên", "012": "Lai Châu",
    "014": "Sơn La", "015": "Yên Bái", "017": "Hòa Bình", "019": "Thái Nguyên",
    "020": "Lạng Sơn", "022": "Quảng Ninh", "024": "Bắc Giang", "025": "Phú Thọ",
    "026": "Vĩnh Phúc", "027": "Bắc Ninh", "030": "Hải Dương", "031": "Hải Phòng",
    "033": "Hưng Yên", "034": "Thái Bình", "035": "Hà Nam", "036": "Nam Định",
    "037": "Ninh Bình", "038": "Thanh Hóa", "040": "Nghệ An", "042": "Hà Tĩnh",
    "044": "Quảng Bình", "045": "Quảng Trị", "046": "Thừa Thiên Huế", "048": "Đà Nẵng",
    "049": "Quảng Nam", "051": "Quảng Ngãi", "052": "Bình Định", "054": "Phú Yên",
    "056": "Khánh Hòa", "058": "Ninh Thuận", "060": "Bình Thuận", "062": "Kon Tum",
    "064": "Gia Lai", "066": "Đắk Lắk", "067": "Đắk Nông", "068": "Lâm Đồng",
    "070": "Bình Phước", "072": "Tây Ninh", "074": "Bình Dương", "075": "Đồng Nai",
    "077": "Bà Rịa - Vũng Tàu", "079": "Hồ Chí Minh", "080": "Long An", "082": "Tiền Giang",
    "083": "Bến Tre", "084": "Trà Vinh", "086": "Vĩnh Long", "087": "Đồng Tháp",
    "089": "An Giang", "091": "Kiên Giang", "092": "Cần Thơ", "093": "Hậu Giang",
    "094": "Sóc Trăng", "095": "Bạc Liêu", "096": "Cà Mau"
}

def validate_format(cccd_number: str) -> dict:
    if not isinstance(cccd_number, str) or not re.match(r"^\d{12}$", cccd_number):
        return {"valid": False, "error": "Invalid format. Must be 12 digits."}

    province_code = cccd_number[0:3]
    gender_code = cccd_number[3]
    year_code = cccd_number[4:6]

    if province_code not in PROVINCES:
        return {"valid": False, "error": f"Invalid province code: {province_code}"}

    gender_map = {
        "0": ("Male", 1900),
        "1": ("Female", 1900),
        "2": ("Male", 2000),
        "3": ("Female", 2000),
        "4": ("Male", 2100),
        "5": ("Female", 2100),
        "6": ("Male", 2200),
        "7": ("Female", 2200),
        "8": ("Male", 2300),
        "9": ("Female", 2300),
    }

    if gender_code not in gender_map:
        return {"valid": False, "error": f"Invalid gender code: {gender_code}"}

    gender, century = gender_map[gender_code]
    birth_year = century + int(year_code)

    return {
        "valid": True,
        "province": PROVINCES[province_code],
        "gender": gender,
        "birth_year": birth_year
    }
