import re

PROVINCES = {
    "001": "Ha Noi", "002": "Ha Giang", "004": "Cao Bang", "006": "Bac Kan",
    "008": "Tuyen Quang", "010": "Lao Cai", "011": "Dien Bien", "012": "Lai Chau",
    "014": "Son La", "015": "Yen Bai", "017": "Hoa Binh", "019": "Thai Nguyen",
    "020": "Lang Son", "022": "Quang Ninh", "024": "Bac Giang", "025": "Phu Tho",
    "026": "Vinh Phuc", "027": "Bac Ninh", "030": "Hai Duong", "031": "Hai Phong",
    "033": "Hung Yen", "034": "Thai Binh", "035": "Ha Nam", "036": "Nam Dinh",
    "037": "Ninh Binh", "038": "Thanh Hoa", "040": "Nghe An", "042": "Ha Tinh",
    "044": "Quang Binh", "045": "Quang Tri", "046": "Thua Thien Hue", "048": "Da Nang",
    "049": "Quang Nam", "051": "Quang Ngai", "052": "Binh Dinh", "054": "Phu Yen",
    "056": "Khanh Hoa", "058": "Ninh Thuan", "060": "Binh Thuan", "062": "Kon Tum",
    "064": "Gia Lai", "066": "Dak Lak", "067": "Dak Nong", "068": "Lam Dong",
    "070": "Binh Phuoc", "072": "Tay Ninh", "074": "Binh Duong", "075": "Dong Nai",
    "077": "Ba Ria - Vung Tau", "079": "Ho Chi Minh", "080": "Long An", "082": "Tien Giang",
    "083": "Ben Tre", "084": "Tra Vinh", "086": "Vinh Long", "087": "Dong Thap",
    "089": "An Giang", "091": "Kien Giang", "092": "Can Tho", "093": "Hau Giang",
    "094": "Soc Trang", "095": "Bac Lieu", "096": "Ca Mau"
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
