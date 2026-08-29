REGIONS = [
    ("DE-BW", "Baden-Württemberg"), ("DE-BY", "Bayern"), ("DE-BE", "Berlin"),
    ("DE-BB", "Brandenburg"), ("DE-HB", "Bremen"), ("DE-HH", "Hamburg"),
    ("DE-HE", "Hessen"), ("DE-MV", "Mecklenburg-Vorpommern"),
    ("DE-NI", "Niedersachsen"), ("DE-NW", "Nordrhein-Westfalen"),
    ("DE-RP", "Rheinland-Pfalz"), ("DE-SL", "Saarland"), ("DE-SN", "Sachsen"),
    ("DE-ST", "Sachsen-Anhalt"), ("DE-SH", "Schleswig-Holstein"),
    ("DE-TH", "Thüringen"),
]

CITIES = [
    ("BER", "Berlin", "DE-BE", 52.5200, 13.4050),
    ("POT", "Potsdam", "DE-BB", 52.3906, 13.0645),
    ("CB", "Cottbus", "DE-BB", 51.7563, 14.3329),
    ("HAM", "Hamburg", "DE-HH", 53.5511, 9.9937),
    ("BRE", "Bremen", "DE-HB", 53.0793, 8.8017),
    ("BHV", "Bremerhaven", "DE-HB", 53.5396, 8.5809),
    ("MUC", "München", "DE-BY", 48.1351, 11.5820),
    ("NUE", "Nürnberg", "DE-BY", 49.4521, 11.0767),
    ("AUG", "Augsburg", "DE-BY", 48.3705, 10.8978),
    ("REG", "Regensburg", "DE-BY", 49.0134, 12.1016),
    ("STR", "Stuttgart", "DE-BW", 48.7758, 9.1829),
    ("HD", "Heidelberg", "DE-BW", 49.3988, 8.6724),
    ("MAN", "Mannheim", "DE-BW", 49.4875, 8.4660),
    ("FRE", "Freiburg im Breisgau", "DE-BW", 47.9990, 7.8421),
    ("FRA", "Frankfurt am Main", "DE-HE", 50.1109, 8.6821),
    ("WIE", "Wiesbaden", "DE-HE", 50.0782, 8.2398),
    ("KAS", "Kassel", "DE-HE", 51.3127, 9.4797),
    ("CGN", "Köln", "DE-NW", 50.9375, 6.9603),
    ("DUS", "Düsseldorf", "DE-NW", 51.2277, 6.7735),
    ("DOR", "Dortmund", "DE-NW", 51.5136, 7.4653),
    ("ESS", "Essen", "DE-NW", 51.4556, 7.0116),
    ("BON", "Bonn", "DE-NW", 50.7374, 7.0982),
    ("HAN", "Hannover", "DE-NI", 52.3759, 9.7320),
    ("BRA", "Braunschweig", "DE-NI", 52.2689, 10.5268),
    ("OLD", "Oldenburg", "DE-NI", 53.1435, 8.2146),
    ("KIE", "Kiel", "DE-SH", 54.3233, 10.1228),
    ("LUE", "Lübeck", "DE-SH", 53.8655, 10.6866),
    ("FL", "Flensburg", "DE-SH", 54.7937, 9.4469),
    ("SCH", "Schwerin", "DE-MV", 53.6355, 11.4012),
    ("ROS", "Rostock", "DE-MV", 54.0924, 12.0991),
    ("GRE", "Greifswald", "DE-MV", 54.0958, 13.3815),
    ("LEI", "Leipzig", "DE-SN", 51.3397, 12.3731),
    ("DRE", "Dresden", "DE-SN", 51.0504, 13.7373),
    ("CHE", "Chemnitz", "DE-SN", 50.8278, 12.9214),
    ("MAG", "Magdeburg", "DE-ST", 52.1205, 11.6276),
    ("HAL", "Halle (Saale)", "DE-ST", 51.4969, 11.9688),
    ("DES", "Dessau-Roßlau", "DE-ST", 51.8308, 12.2426),
    ("ERF", "Erfurt", "DE-TH", 50.9848, 11.0299),
    ("JEN", "Jena", "DE-TH", 50.9271, 11.5892),
    ("GE", "Gera", "DE-TH", 50.8772, 12.0810),
    ("MAI", "Mainz", "DE-RP", 49.9929, 8.2473),
    ("KOB", "Koblenz", "DE-RP", 50.3569, 7.5890),
    ("TRI", "Trier", "DE-RP", 49.7499, 6.6371),
    ("SAA", "Saarbrücken", "DE-SL", 49.2402, 6.9969),
    ("NEU", "Neunkirchen", "DE-SL", 49.3445, 7.1806),
]

LEGAL_FORMS = [
    ("EU", "Einzelunternehmen", "SOLE_PROPRIETORSHIP"),
    ("EK", "Eingetragener Kaufmann / Eingetragene Kauffrau (e.K.)", "SOLE_PROPRIETORSHIP"),
    ("GBR", "Gesellschaft bürgerlichen Rechts (GbR)", "PARTNERSHIP"),
    ("OHG", "Offene Handelsgesellschaft (OHG)", "PARTNERSHIP"),
    ("KG", "Kommanditgesellschaft (KG)", "PARTNERSHIP"),
    ("GMBH", "Gesellschaft mit beschränkter Haftung (GmbH)", "CORPORATION"),
    ("UG", "Unternehmergesellschaft (haftungsbeschränkt)", "CORPORATION"),
    ("GMBHCO", "GmbH & Co. KG", "PARTNERSHIP"),
    ("AG", "Aktiengesellschaft (AG)", "CORPORATION"),
    ("KGaA", "Kommanditgesellschaft auf Aktien (KGaA)", "CORPORATION"),
    ("SE", "Europäische Gesellschaft (SE)", "CORPORATION"),
    ("EG", "Eingetragene Genossenschaft (eG)", "COOPERATIVE"),
    ("EV", "Eingetragener Verein (e.V.)", "ASSOCIATION"),
    ("STIFT", "Stiftung", "FOUNDATION"),
]

INDUSTRIES = [
    ("MAN", "Manufacturing"), ("RET", "Retail"), ("WHO", "Wholesale"),
    ("CON", "Construction"), ("LOG", "Transport and logistics"),
    ("HOS", "Hospitality"), ("TEC", "Software and IT services"),
    ("PRO", "Professional services"), ("MED", "Healthcare"),
    ("EDU", "Education"), ("REA", "Real estate"), ("ENE", "Energy"),
    ("AGR", "Agriculture"), ("MEDIA", "Media and creative industries"),
    ("AUT", "Automotive"), ("MAR", "Maritime and port services"),
    ("NON", "Non-profit"), ("HLD", "Holding company"),
]

SERVICES = [
    ("FIA", "Financial accounting", "MONTHLY"),
    ("AP", "Accounts payable", "MONTHLY"),
    ("AR", "Accounts receivable", "MONTHLY"),
    ("VAT", "VAT return", "MONTHLY_OR_QUARTERLY"),
    ("PAY", "Payroll", "MONTHLY"),
    ("MGT", "Management reporting", "MONTHLY"),
    ("AFS", "Annual financial statements", "ANNUAL"),
    ("CTR", "Corporate tax return", "ANNUAL"),
    ("ADV", "Advisory", "ON_DEMAND"),
    ("FORM", "Company formation", "ONE_OFF"),
    ("CLOSE", "Company closure", "ONE_OFF"),
]

DOCUMENT_TYPES = [
    ("SALES_INV", "Sales invoice"), ("PURCHASE_INV", "Purchase invoice"),
    ("BANK_STMT", "Bank statement"), ("RECEIPT", "Receipt"),
    ("PAYROLL", "Payroll file"), ("CONTRACT", "Contract"),
    ("TAX_NOTICE", "Tax notice"), ("EXPENSE", "Expense claim"),
]

TASK_TYPES = [
    ("BOOKKEEP", "Bookkeeping"), ("BANK_REC", "Bank reconciliation"),
    ("INV_VALIDATE", "Invoice validation"), ("PAYROLL", "Payroll processing"),
    ("VAT_PREP", "VAT return preparation"), ("MONTH_CLOSE", "Month-end close"),
    ("YEAR_CLOSE", "Year-end close"), ("REVIEW", "Review"),
    ("CLARIFY", "Client clarification"), ("CORRECTION", "Correction"),
]

GL_ACCOUNTS = [
    ("1000", "Bank", "ASSET"), ("1200", "Accounts receivable", "ASSET"),
    ("1400", "Input VAT", "ASSET"), ("1600", "Accounts payable", "LIABILITY"),
    ("1776", "Output VAT", "LIABILITY"), ("2000", "Share capital", "EQUITY"),
    ("3000", "Sales revenue", "REVENUE"),
    ("4000", "Cost of materials and external services", "EXPENSE"),
    ("4200", "Rent expense", "EXPENSE"), ("4300", "Payroll expense", "EXPENSE"),
    ("4400", "Bank fees", "EXPENSE"), ("4500", "Other expenses", "EXPENSE"),
]

CURRENCIES = ["EUR", "USD", "GBP", "CHF", "PLN", "CZK", "SEK", "NOK", "DKK"]

EMPLOYEE_ROLES = {
    "HEAD": "Head",
    "CM_JR": "Junior client manager",
    "CM_SR": "Senior client manager",
    "ACC_JR": "Junior accountant",
    "ACC_SR": "Senior accountant",
}
