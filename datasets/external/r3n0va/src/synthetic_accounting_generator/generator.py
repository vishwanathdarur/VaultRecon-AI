from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from .references import (
    CITIES, CURRENCIES, DOCUMENT_TYPES, EMPLOYEE_ROLES, GL_ACCOUNTS,
    INDUSTRIES, LEGAL_FORMS, REGIONS, SERVICES, TASK_TYPES,
)
from .utils import (
    IdFactory, ascii_email_token, company_name, d, dt, money, month_end,
    month_starts, person_name, random_date, random_datetime, synthetic_iban,
    synthetic_vat_id, weighted_choice,
)
from .writer import DatasetWriter


class AccountingDatasetGenerator:
    def __init__(self, config: dict, output_dir: Path) -> None:
        self.config = config
        self.output_dir = output_dir
        self.rng = random.Random(int(config["project"]["seed"]))
        self.ids = IdFactory()
        self.months = month_starts(
            date.fromisoformat(str(config["project"]["start_date"])),
            int(config["project"]["months"]),
        )
        self.scenario = config.get("scenario", {}).get("multipliers", {})
        self.writer = DatasetWriter(
            output_dir,
            delimiter=str(config["output"].get("csv_delimiter", ",")),
            overwrite=bool(config["output"].get("overwrite", True)),
        )
        self.firms = []
        self.offices = []
        self.employees = []
        self.clients = []
        self.assignments = []
        self.contracts = []
        self.contract_services = []
        self.bank_accounts = []
        self.counterparties = []
        self.dq_issues = []
        self.dq_rule_counts: dict[str, int] = {}
        self.used_company_names: set[str] = set()
        runtime = config.get("runtime", {})
        self.progress_enabled = bool(runtime.get("progress", True))
        self.progress_every_clients = max(
            1,
            int(runtime.get("progress_every_clients", 100)),
        )

    def multiplier(self, name: str) -> float:
        return float(self.scenario.get(name, 1.0))

    def minimum_dq_issues(self, rule_code: str) -> int:
        minimums = self.config.get("data_quality", {}).get(
            "minimum_issues_per_rule",
            {},
        )
        return max(0, int(minimums.get(rule_code, 0)))

    def needs_minimum_dq_issue(self, rule_code: str) -> bool:
        return (
            self.config.get("data_quality", {}).get("mode") == "quality-test"
            and self.dq_rule_counts.get(rule_code, 0)
            < self.minimum_dq_issues(rule_code)
        )

    def log(self, message: str) -> None:
        if self.progress_enabled:
            print(f"[generator] {message}", flush=True)

    def unique_client_company_name(
        self,
        legal_form_code: str,
        city_code: str,
    ) -> str:
        for _ in range(120):
            candidate = company_name(self.rng, legal_form_code)
            if candidate not in self.used_company_names:
                self.used_company_names.add(candidate)
                return candidate

        sequence = len(self.used_company_names) + 1
        candidate = company_name(
            self.rng,
            legal_form_code,
            distinguishing_token=f"{city_code}-{sequence:05d}",
        )
        while candidate in self.used_company_names:
            sequence += 1
            candidate = company_name(
                self.rng,
                legal_form_code,
                distinguishing_token=f"{city_code}-{sequence:05d}",
            )
        self.used_company_names.add(candidate)
        return candidate

    def generate(self) -> dict:
        self.log("1/7 reference data")
        self.generate_references()
        self.log("2/7 accounting firms, offices and employees")
        self.generate_firms()
        self.log("3/7 client companies and lifecycle events")
        self.generate_clients()
        self.log("4/7 assignments, contracts, accounts and counterparties")
        self.generate_relationships()
        self.log("5/7 documents, invoices, payments, journals and workflow")
        self.generate_activity()
        self.log("6/7 accounting-practice billing")
        self.generate_firm_billing()
        self.log("7/7 data-quality manifest")
        self.write_dq_manifest()
        self.writer.close()

        manifest = {
            "generator_version": "2.3.0",
            "project_name": self.config["project"]["name"],
            "seed": self.config["project"]["seed"],
            "country_code": self.config["project"]["country_code"],
            "period_start": self.months[0].isoformat(),
            "period_end": month_end(self.months[-1]).isoformat(),
            "scenario": self.config.get("scenario", {}).get("name", "none"),
            "row_counts": self.writer.row_counts,
        }
        (self.output_dir / "generation_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return manifest

    def generate_references(self) -> None:
        for code, name in REGIONS:
            self.writer.write("region", {"region_code": code, "region_name": name})
        for code, name, region, lat, lon in CITIES:
            self.writer.write("city", {
                "city_code": code, "city_name": name, "region_code": region,
                "latitude": lat, "longitude": lon,
            })
        for code, name, category in LEGAL_FORMS:
            self.writer.write("legal_form", {
                "legal_form_code": code, "legal_form_name": name,
                "legal_form_category": category,
            })
        for code, name in INDUSTRIES:
            self.writer.write("industry", {"industry_code": code, "industry_name": name})
        for code in CURRENCIES:
            self.writer.write("currency", {
                "currency_code": code,
                "is_base_currency": code == self.config["project"]["base_currency"],
            })
        for code, name, cadence in SERVICES:
            self.writer.write("service_type", {
                "service_type_code": code, "service_type_name": name,
                "service_cadence": cadence,
            })
        for code, name in DOCUMENT_TYPES:
            self.writer.write("document_type", {
                "document_type_code": code, "document_type_name": name,
            })
        for code, name in TASK_TYPES:
            self.writer.write("task_type", {
                "task_type_code": code, "task_type_name": name,
            })
        for code, name, account_type in GL_ACCOUNTS:
            self.writer.write("gl_account", {
                "gl_account_code": code, "gl_account_name": name,
                "account_type": account_type,
            })

        base_rates = {
            "EUR": 1.0, "USD": 0.92, "GBP": 1.17, "CHF": 1.04,
            "PLN": 0.23, "CZK": 0.040, "SEK": 0.088,
            "NOK": 0.086, "DKK": 0.134,
        }
        for month in self.months:
            for currency in CURRENCIES:
                self.writer.write("fx_rate", {
                    "rate_month": d(month),
                    "currency_code": currency,
                    "eur_rate": round(
                        base_rates[currency] * (1 + self.rng.uniform(-0.035, 0.035)),
                        6,
                    ),
                })

    def allocate_roles(self, employee_count: int) -> list[str]:
        cfg = self.config["firms"]["roles"]
        roles = ["HEAD"]
        remaining = employee_count - 1
        for role in ("CM_SR", "CM_JR", "ACC_SR"):
            target = max(
                int(cfg[role]["min_per_firm"]),
                round(employee_count * float(cfg[role]["share"])),
            )
            take = min(remaining, target)
            roles.extend([role] * take)
            remaining -= take
        roles.extend(["ACC_JR"] * max(0, remaining))
        return roles[:employee_count]

    def generate_firms(self) -> None:
        for size_class in ("small", "medium", "large"):
            block = self.config["firms"][size_class]
            for _ in range(int(block.get("count", 0))):
                firm_id = self.ids.next("FIRM")
                headquarters = self.rng.choice(CITIES)
                office_count = self.rng.randint(
                    int(block["offices"]["min"]), int(block["offices"]["max"])
                )
                employee_count = self.rng.randint(
                    int(block["employees"]["min"]), int(block["employees"]["max"])
                )
                founded = date(self.rng.randint(1995, 2020), self.rng.randint(1, 12), 1)
                firm = {
                    "firm_id": firm_id,
                    "firm_name": f"{headquarters[1]} Accounting Partners {firm_id[-3:]}",
                    "size_class": size_class.upper(),
                    "headquarters_city_code": headquarters[0],
                    "founded_date": d(founded),
                    "base_currency": self.config["project"]["base_currency"],
                    "configured_client_min": block["clients"]["min"],
                    "configured_client_max": block["clients"]["max"],
                }
                self.writer.write("accounting_firm", firm)
                self.firms.append(firm)

                other_cities = [city for city in CITIES if city[0] != headquarters[0]]
                office_cities = [headquarters] + self.rng.sample(
                    other_cities, k=max(0, office_count - 1)
                )
                firm_offices = []
                for index, city in enumerate(office_cities):
                    office = {
                        "office_id": self.ids.next("OFF"),
                        "firm_id": firm_id,
                        "office_name": f"{city[1]} Office",
                        "city_code": city[0],
                        "is_headquarters": index == 0,
                        "opened_date": d(founded),
                    }
                    self.writer.write("office", office)
                    self.offices.append(office)
                    firm_offices.append(office)

                employment = self.config["firms"]["employment"]
                latest_start = min(
                    date(2022, 12, 31),
                    self.months[0] - timedelta(days=1),
                )
                earliest_start = max(founded, date(2010, 1, 1))
                for role in self.allocate_roles(employee_count):
                    employee_id = self.ids.next("EMP")
                    first, last = person_name(self.rng)
                    office = (
                        firm_offices[0]
                        if role == "HEAD"
                        else self.rng.choice(firm_offices)
                    )
                    employee = {
                        "employee_id": employee_id,
                        "firm_id": firm_id,
                        "office_id": office["office_id"],
                        "role_code": role,
                        "role_name": EMPLOYEE_ROLES[role],
                        "first_name": first,
                        "last_name": last,
                        "email": (
                            f"{ascii_email_token(first)}."
                            f"{ascii_email_token(last)}."
                            f"{employee_id[-6:]}@synthetic-accounting.de"
                        ),
                        "employment_start_date": d(
                            random_date(
                                self.rng,
                                earliest_start,
                                latest_start,
                            )
                        ),
                        "employment_end_date": "",
                        "contract_type": employment["contract_type"],
                        "weekly_hours": self.rng.choices(
                            employment["weekly_hours_options"],
                            weights=employment["weekly_hours_weights"],
                            k=1,
                        )[0],
                        "hourly_cost_eur": money(
                            {
                                "HEAD": 85,
                                "CM_SR": 52,
                                "CM_JR": 35,
                                "ACC_SR": 48,
                                "ACC_JR": 32,
                            }[role]
                            * self.rng.uniform(0.92, 1.12)
                        ),
                    }
                    self.writer.write("employee", employee)
                    self.employees.append(employee)

    def generate_clients(self) -> None:
        legal_weights = self.config["clients"]["legal_form_weights"]
        period_end = month_end(self.months[-1])
        total_created = 0

        for firm in self.firms:
            size_key = firm["size_class"].lower()
            block = self.config["firms"][size_key]
            count = self.rng.randint(
                int(block["clients"]["min"]),
                int(block["clients"]["max"]),
            )
            count = max(
                1,
                round(count * self.multiplier("client_growth")),
            )
            firm_offices = [
                office
                for office in self.offices
                if office["firm_id"] == firm["firm_id"]
            ]

            for _ in range(count):
                client_id = self.ids.next("CLI")
                legal_form = weighted_choice(self.rng, legal_weights)
                city = self.rng.choice(CITIES)
                industry = self.rng.choice(INDUSTRIES)[0]
                distribution = self.config["clients"]["employee_distribution"]
                employees = int(
                    max(
                        int(self.config["clients"]["employees"]["min"]),
                        min(
                            int(self.config["clients"]["employees"]["max"]),
                            self.rng.lognormvariate(
                                float(distribution["lognormal_mu"]),
                                float(distribution["lognormal_sigma"]),
                            ),
                        ),
                    )
                )
                if (
                    industry in {"MAN", "MAR", "AUT", "ENE"}
                    and self.rng.random()
                    < float(distribution["large_employer_probability"])
                ):
                    employees = self.rng.randint(
                        150,
                        int(self.config["clients"]["employees"]["max"]),
                    )

                complexity = weighted_choice(
                    self.rng,
                    self.config["clients"]["complexity_weights"],
                )
                risk = weighted_choice(
                    self.rng,
                    self.config["clients"]["risk_weights"],
                )
                digital = weighted_choice(
                    self.rng,
                    self.config["clients"]["digital_maturity_weights"],
                )
                lifecycle = weighted_choice(
                    self.rng,
                    self.config["clients"]["lifecycle_weights"],
                )

                onboarding_latest = period_end - timedelta(
                    days=60 if lifecycle == "TERMINATED" else 20
                )
                onboarding = random_date(
                    self.rng,
                    date(2018, 1, 1),
                    onboarding_latest,
                )
                incorporation = random_date(
                    self.rng,
                    date(1970, 1, 1),
                    onboarding,
                )

                annual_revenue = max(
                    25_000,
                    employees * self.rng.uniform(60_000, 220_000),
                )
                if industry == "HLD":
                    annual_revenue *= self.rng.uniform(0.05, 0.40)
                volume_band = (
                    "MICRO"
                    if annual_revenue < 250_000
                    else "SMALL"
                    if annual_revenue < 2_000_000
                    else "MEDIUM"
                    if annual_revenue < 20_000_000
                    else "LARGE"
                )

                foreign_probability = min(
                    1.0,
                    float(
                        self.config["clients"][
                            "foreign_trade_probability"
                        ]
                    )
                    * self.multiplier("foreign_trade"),
                )
                vat_registered = self.rng.random() < 0.88
                if self.needs_minimum_dq_issue("MISSING_VAT_ID"):
                    vat_registered = True
                vat_id = (
                    synthetic_vat_id(client_id)
                    if vat_registered
                    else ""
                )

                termination_date = ""
                if lifecycle == "TERMINATED":
                    termination_date = d(
                        random_date(
                            self.rng,
                            max(
                                onboarding + timedelta(days=30),
                                self.months[0],
                            ),
                            period_end,
                        )
                    )

                client = {
                    "client_id": client_id,
                    "firm_id": firm["firm_id"],
                    "primary_office_id": self.rng.choice(
                        firm_offices
                    )["office_id"],
                    "company_name": self.unique_client_company_name(
                        legal_form,
                        city[0],
                    ),
                    "legal_form_code": legal_form,
                    "industry_code": industry,
                    "city_code": city[0],
                    "incorporation_date": d(incorporation),
                    "employee_count": employees,
                    "annual_revenue_estimate_eur": money(
                        annual_revenue
                    ),
                    "transaction_volume_band": volume_band,
                    "vat_registered": vat_registered,
                    "vat_id": vat_id,
                    "accounting_complexity": complexity,
                    "risk_category": risk,
                    "digital_maturity": digital,
                    "preferred_channel": self.rng.choice(
                        ["EMAIL", "PORTAL", "PHONE", "MEETING"]
                    ),
                    "lifecycle_status": lifecycle,
                    "onboarding_date": d(onboarding),
                    "termination_date": termination_date,
                    "base_currency": "EUR",
                    "foreign_trade_flag": (
                        self.rng.random() < foreign_probability
                    ),
                }

                if self.config["data_quality"]["mode"] == "quality-test":
                    probability = (
                        float(
                            self.config["data_quality"]["injection"][
                                "missing_vat_id_probability"
                            ]
                        )
                        * self.multiplier("dq_injection")
                    )
                    if (
                        client["vat_registered"]
                        and (
                            self.needs_minimum_dq_issue("MISSING_VAT_ID")
                            or self.rng.random() < probability
                        )
                    ):
                        client["vat_id"] = ""
                        self.record_dq(
                            "client_company",
                            client_id,
                            "MISSING_VAT_ID",
                            "VAT-registered client has no VAT ID",
                        )

                self.writer.write("client_company", client)
                self.clients.append(client)

                contact_id = self.ids.next("CON")
                first, last = person_name(self.rng)
                self.writer.write(
                    "client_contact",
                    {
                        "contact_id": contact_id,
                        "client_id": client_id,
                        "first_name": first,
                        "last_name": last,
                        "role_title": self.rng.choice(
                            [
                                "Managing Director",
                                "Finance Manager",
                                "Owner",
                                "Office Manager",
                            ]
                        ),
                        "email": (
                            f"{ascii_email_token(first)}."
                            f"{ascii_email_token(last)}."
                            f"{contact_id[-6:]}@example-client.de"
                        ),
                        "phone": (
                            f"+49-{self.rng.randint(30, 9999)}-"
                            f"{self.rng.randint(100000, 9999999)}"
                        ),
                        "is_primary": True,
                    },
                )

                activation_date = onboarding + timedelta(
                    days=self.rng.randint(5, 20)
                )
                signed_date = min(
                    activation_date,
                    onboarding
                    + timedelta(days=self.rng.randint(1, 10)),
                )
                for event_type, event_date in [
                    ("ONBOARDING_STARTED", onboarding),
                    ("CONTRACT_SIGNED", signed_date),
                    ("ACCOUNT_ACTIVATED", activation_date),
                ]:
                    self.writer.write(
                        "client_event",
                        {
                            "client_event_id": self.ids.next("CEV"),
                            "client_id": client_id,
                            "event_date": d(event_date),
                            "event_type": event_type,
                            "event_reason": "",
                        },
                    )

                if lifecycle == "TERMINATED":
                    self.writer.write(
                        "client_event",
                        {
                            "client_event_id": self.ids.next("CEV"),
                            "client_id": client_id,
                            "event_date": client["termination_date"],
                            "event_type": "CONTRACT_TERMINATED",
                            "event_reason": self.rng.choice(
                                [
                                    "PRICE",
                                    "SERVICE_QUALITY",
                                    "CLIENT_CLOSED",
                                    "INSOURCING",
                                    "OTHER",
                                ]
                            ),
                        },
                    )

                total_created += 1
                if (
                    total_created % self.progress_every_clients == 0
                ):
                    self.log(
                        f"generated {total_created} client companies"
                    )

            self.log(
                f"{firm['firm_id']} ({firm['size_class']}): "
                f"{count} clients"
            )

    def generate_relationships(self) -> None:
        for client_index, client in enumerate(self.clients, start=1):
            if client_index % self.progress_every_clients == 0:
                self.log(
                    f"prepared relationships for "
                    f"{client_index}/{len(self.clients)} clients"
                )
            firm_employees = [
                employee for employee in self.employees
                if employee["firm_id"] == client["firm_id"]
            ]
            managers = [
                employee for employee in firm_employees
                if employee["role_code"] in {"CM_JR", "CM_SR"}
            ]
            accountants = [
                employee for employee in firm_employees
                if employee["role_code"] in {"ACC_JR", "ACC_SR"}
            ]
            manager = self.rng.choice(managers)
            accountant = self.rng.choice(accountants)
            assignment = {
                "assignment_id": self.ids.next("ASN"),
                "client_id": client["client_id"],
                "client_manager_id": manager["employee_id"],
                "accountant_id": accountant["employee_id"],
                "assignment_start_date": client["onboarding_date"],
                "assignment_end_date": "",
                "is_current": True,
            }
            self.writer.write("client_assignment", assignment)
            self.assignments.append(assignment)

            complexity_multiplier = float(
                self.config["pricing"]["complexity_multiplier"][
                    client["accounting_complexity"]
                ]
            )
            size_factor = max(1.0, int(client["employee_count"]) ** 0.35)
            raw_base = 140 + 32 * size_factor * complexity_multiplier
            fee_cfg = self.config["pricing"]["monthly_base_fee"]
            base_fee = min(
                float(fee_cfg["max"]), max(float(fee_cfg["min"]), raw_base)
            )
            contract = {
                "contract_id": self.ids.next("CTR"),
                "client_id": client["client_id"],
                "firm_id": client["firm_id"],
                "start_date": client["onboarding_date"],
                "end_date": client["termination_date"],
                "status": (
                    "TERMINATED"
                    if client["lifecycle_status"] == "TERMINATED"
                    else "ACTIVE"
                ),
                "billing_model": "BASE_PLUS_USAGE",
                "monthly_base_fee_eur": money(base_fee),
                "included_transaction_count": round(30 + 18 * size_factor),
                "overage_rate_eur": money(
                    self.rng.uniform(
                        float(self.config["pricing"]["transaction_fee"]["min"]),
                        float(self.config["pricing"]["transaction_fee"]["max"]),
                    )
                ),
                "sla_tier": weighted_choice(
                    self.rng, self.config["pricing"]["sla_tier_weights"]
                ),
                "discount_pct": self.rng.choice(
                    self.config["pricing"]["discount_options_pct"]
                ),
            }
            self.writer.write("service_contract", contract)
            self.contracts.append(contract)

            services = {"FIA", "VAT"}
            adoption = self.config["services"]["adoption"]
            if int(client["employee_count"]) > 1 and self.rng.random() < float(adoption["PAY"]):
                services.add("PAY")
            if client["transaction_volume_band"] in {"MEDIUM", "LARGE"}:
                if self.rng.random() < float(adoption["AP"]):
                    services.add("AP")
                if self.rng.random() < float(adoption["AR"]):
                    services.add("AR")
            for optional in ("MGT", "AFS", "CTR", "ADV"):
                if self.rng.random() < float(adoption[optional]):
                    services.add(optional)
            services = {
                service for service in services
                if self.config["services"]["enabled"].get(service, False)
            }
            shares = {
                "FIA": 0.55, "VAT": 0.12, "PAY": 0.25, "AP": 0.18,
                "AR": 0.18, "MGT": 0.30, "AFS": 0.20, "CTR": 0.15,
                "ADV": 0.10,
            }
            for service in sorted(services):
                row = {
                    "contract_service_id": self.ids.next("CSV"),
                    "contract_id": contract["contract_id"],
                    "service_type_code": service,
                    "service_start_date": contract["start_date"],
                    "service_end_date": contract["end_date"],
                    "monthly_fee_eur": money(base_fee * shares.get(service, 0.10)),
                    "is_active": contract["status"] == "ACTIVE",
                }
                self.writer.write("contract_service", row)
                self.contract_services.append(row)

            currencies = ["EUR"]
            if (
                client["foreign_trade_flag"]
                and self.rng.random()
                < float(self.config["clients"]["foreign_account_probability"])
            ):
                currencies += self.rng.sample(
                    self.config["clients"]["foreign_currencies"],
                    k=self.rng.randint(
                        1, min(2, len(self.config["clients"]["foreign_currencies"]))
                    ),
                )
            for currency in currencies:
                account = {
                    "bank_account_id": self.ids.next("BAC"),
                    "client_id": client["client_id"],
                    "iban": synthetic_iban(f"{client['client_id']}-{currency}"),
                    "currency_code": currency,
                    "bank_name": self.rng.choice([
                        "Rhein Business Bank", "Hanseatic Commercial Bank",
                        "Europa Mittelstand Bank", "German Trade Bank",
                    ]),
                    "opening_balance": money(
                        self.rng.uniform(5_000, 800_000)
                        if currency == "EUR"
                        else self.rng.uniform(2_000, 150_000)
                    ),
                    "opened_date": client["onboarding_date"],
                    "closed_date": "",
                    "status": "ACTIVE",
                }
                self.writer.write("bank_account", account)
                self.bank_accounts.append(account)

            counterparty_count = max(
                3,
                min(
                    25,
                    int(int(client["employee_count"]) ** 0.5 * 2 + self.rng.randint(2, 8)),
                ),
            )
            for _ in range(counterparty_count):
                foreign = client["foreign_trade_flag"] and self.rng.random() < 0.18
                cp = {
                    "counterparty_id": self.ids.next("CP"),
                    "client_id": client["client_id"],
                    "counterparty_name": company_name(
                        self.rng, self.rng.choice(["GMBH", "UG", "AG", "EK"])
                    ),
                    "counterparty_type": self.rng.choice(["CUSTOMER", "SUPPLIER"]),
                    "country_code": (
                        "DE"
                        if not foreign
                        else self.rng.choice(["AT", "NL", "FR", "PL", "CH", "GB", "US"])
                    ),
                    "currency_code": (
                        "EUR"
                        if not foreign
                        else self.rng.choice(
                            self.config["clients"]["foreign_currencies"]
                        )
                    ),
                    "risk_category": weighted_choice(
                        self.rng, {"LOW": 0.70, "MEDIUM": 0.25, "HIGH": 0.05}
                    ),
                }
                self.writer.write("counterparty", cp)
                self.counterparties.append(cp)

    def generate_activity(self) -> None:
        invoice_ranges = self.config["activity"]["invoices_per_month"]
        late_probability = min(
            0.95,
            float(self.config["activity"]["late_document_probability"])
            * self.multiplier("document_delay"),
        )
        workload_multiplier = self.multiplier("workload")
        payment_delay_multiplier = self.multiplier("payment_delay")

        for client_index, client in enumerate(self.clients, start=1):
            if client_index % self.progress_every_clients == 0:
                self.log(
                    f"generated activity for "
                    f"{client_index}/{len(self.clients)} clients"
                )
            contract = next(
                row for row in self.contracts
                if row["client_id"] == client["client_id"]
            )
            assignment = next(
                row for row in self.assignments
                if row["client_id"] == client["client_id"]
            )
            accounts = [
                row for row in self.bank_accounts
                if row["client_id"] == client["client_id"]
            ]
            counterparties = [
                row for row in self.counterparties
                if row["client_id"] == client["client_id"]
            ]
            customers = [
                row for row in counterparties if row["counterparty_type"] == "CUSTOMER"
            ] or counterparties
            suppliers = [
                row for row in counterparties if row["counterparty_type"] == "SUPPLIER"
            ] or counterparties
            range_cfg = invoice_ranges[client["transaction_volume_band"]]

            for month in self.months:
                onboarding = date.fromisoformat(client["onboarding_date"])
                if onboarding > month_end(month):
                    continue
                if (
                    client["termination_date"]
                    and date.fromisoformat(client["termination_date"]) < month
                ):
                    continue

                quarter_multiplier = (
                    float(self.config["activity"]["quarter_end_multiplier"])
                    if month.month in {3, 6, 9, 12}
                    else 1.0
                )
                sales_count = max(
                    1,
                    round(
                        self.rng.randint(
                            int(range_cfg["min"]), int(range_cfg["max"])
                        )
                        * quarter_multiplier
                    ),
                )
                ratio_cfg = self.config["activity"]["purchase_to_sales_ratio"]
                purchase_count = max(
                    1,
                    round(
                        sales_count
                        * self.rng.uniform(
                            float(ratio_cfg["min"]), float(ratio_cfg["max"])
                        )
                    ),
                )

                monthly_invoices = []
                late_documents = []
                used_document_references: list[str] = []
                for direction, count, pool in [
                    ("AR", sales_count, customers),
                    ("AP", purchase_count, suppliers),
                ]:
                    for _ in range(count):
                        cp = self.rng.choice(pool)
                        issue_date = random_date(self.rng, month, month_end(month))
                        due_date = issue_date + timedelta(
                            days=self.rng.choice([7, 14, 30, 45])
                        )
                        gross = max(
                            35,
                            self.rng.lognormvariate(
                                6.7 if direction == "AR" else 6.4, 1.0
                            ),
                        )
                        if client["transaction_volume_band"] == "LARGE":
                            gross *= self.rng.uniform(3, 12)
                        vat_rate = self.rng.choices(
                            [0.00, 0.07, 0.19], weights=[0.08, 0.12, 0.80], k=1
                        )[0]
                        net = gross / (1 + vat_rate)
                        vat = gross - net
                        is_late = self.rng.random() < late_probability
                        lag = (
                            self.rng.randint(8, 22)
                            if is_late
                            else self.rng.randint(0, 5)
                        )
                        received_date = issue_date + timedelta(days=lag)
                        document_id = self.ids.next("DOC")
                        reference = (
                            f"{direction}-{client['client_id'][-5:]}-"
                            f"{month:%Y%m}-{document_id[-6:]}"
                        )

                        if self.config["data_quality"]["mode"] == "quality-test":
                            probability = (
                                float(
                                    self.config["data_quality"]["injection"][
                                        "duplicate_document_reference_probability"
                                    ]
                                )
                                * self.multiplier("dq_injection")
                            )
                            if (
                                used_document_references
                                and (
                                    self.needs_minimum_dq_issue(
                                        "DUPLICATE_DOCUMENT_REFERENCE"
                                    )
                                    or self.rng.random() < probability
                                )
                            ):
                                reference = self.rng.choice(
                                    used_document_references
                                )
                                self.record_dq(
                                    "accounting_document",
                                    document_id,
                                    "DUPLICATE_DOCUMENT_REFERENCE",
                                    "Injected duplicate document reference",
                                )

                        document = {
                            "document_id": document_id,
                            "client_id": client["client_id"],
                            "document_type_code": (
                                "SALES_INV" if direction == "AR" else "PURCHASE_INV"
                            ),
                            "external_reference": reference,
                            "document_date": d(issue_date),
                            "accounting_period": month.strftime("%Y-%m"),
                            "received_timestamp": dt(
                                random_datetime(self.rng, received_date)
                            ),
                            "ingestion_channel": self.rng.choice(
                                ["PORTAL", "EMAIL", "API", "MANUAL"]
                            ),
                            "processing_status": (
                                "LATE" if is_late else "VALIDATED"
                            ),
                            "validation_result": "VALID",
                            "attachment_quality": self.rng.choices(
                                ["GOOD", "ACCEPTABLE", "POOR"],
                                weights=[0.70, 0.25, 0.05],
                                k=1,
                            )[0],
                        }
                        self.writer.write("accounting_document", document)
                        used_document_references.append(reference)
                        if is_late:
                            late_documents.append(document)

                        invoice_id = self.ids.next("INV")
                        invoice = {
                            "invoice_id": invoice_id,
                            "document_id": document_id,
                            "client_id": client["client_id"],
                            "counterparty_id": cp["counterparty_id"],
                            "invoice_direction": direction,
                            "invoice_number": reference,
                            "issue_date": d(issue_date),
                            "due_date": d(due_date),
                            "currency_code": cp["currency_code"],
                            "net_amount": money(net),
                            "vat_rate": vat_rate,
                            "vat_amount": money(vat),
                            "gross_amount": money(gross),
                            "gross_amount_eur": money(gross),
                            "payment_status": "OPEN",
                        }
                        if self.config["data_quality"]["mode"] == "quality-test":
                            probability = (
                                float(
                                    self.config["data_quality"]["injection"][
                                        "invalid_vat_rate_probability"
                                    ]
                                )
                                * self.multiplier("dq_injection")
                            )
                            if (
                                self.needs_minimum_dq_issue("INVALID_VAT_RATE")
                                or self.rng.random() < probability
                            ):
                                invoice["vat_rate"] = 0.25
                                self.record_dq(
                                    "business_invoice", invoice_id,
                                    "INVALID_VAT_RATE",
                                    "Injected unsupported VAT rate",
                                )
                        self.writer.write("business_invoice", invoice)
                        monthly_invoices.append(invoice)

                        if self.config["ledger"]["enabled"]:
                            entry_id = self.ids.next("JE")
                            self.writer.write("journal_entry", {
                                "journal_entry_id": entry_id,
                                "client_id": client["client_id"],
                                "entry_date": d(issue_date),
                                "accounting_period": month.strftime("%Y-%m"),
                                "source_document_id": document_id,
                                "entry_type": f"{direction}_INVOICE",
                                "description": f"{direction} invoice posting",
                                "currency_code": "EUR",
                            })
                            lines = (
                                [
                                    ("1200", gross, 0),
                                    ("3000", 0, net),
                                    ("1776", 0, vat),
                                ]
                                if direction == "AR"
                                else [
                                    ("4000", net, 0),
                                    ("1400", vat, 0),
                                    ("1600", 0, gross),
                                ]
                            )
                            for account_code, debit, credit in lines:
                                self.writer.write("journal_line", {
                                    "journal_line_id": self.ids.next("JL"),
                                    "journal_entry_id": entry_id,
                                    "gl_account_code": account_code,
                                    "debit_amount_eur": money(debit),
                                    "credit_amount_eur": money(credit),
                                    "cost_center_code": f"CC-{client['industry_code']}",
                                })

                for invoice in monthly_invoices:
                    if (
                        self.rng.random()
                        >= float(self.config["activity"]["payment_probability"])
                    ):
                        continue
                    due = date.fromisoformat(invoice["due_date"])
                    risk_delay = {
                        "LOW": 2, "MEDIUM": 8, "HIGH": 18
                    }[client["risk_category"]]
                    delay = round(
                        self.rng.gauss(risk_delay, 8)
                        * payment_delay_multiplier
                    )
                    paid_date = max(
                        date.fromisoformat(invoice["issue_date"]),
                        due + timedelta(days=delay),
                    )
                    amount = float(invoice["gross_amount_eur"])
                    partial = (
                        self.rng.random()
                        < float(
                            self.config["activity"][
                                "partial_payment_probability"
                            ]
                        )
                    )
                    paid_amount = (
                        amount * self.rng.uniform(0.35, 0.80)
                        if partial
                        else amount
                    )
                    self.writer.write("payment", {
                        "payment_id": self.ids.next("PAY"),
                        "invoice_id": invoice["invoice_id"],
                        "client_id": client["client_id"],
                        "payment_date": d(paid_date),
                        "currency_code": invoice["currency_code"],
                        "payment_amount": money(paid_amount),
                        "payment_amount_eur": money(paid_amount),
                        "payment_method": self.rng.choice(
                            ["BANK_TRANSFER", "DIRECT_DEBIT", "CARD"]
                        ),
                        "is_partial": partial,
                    })

                    account = self.rng.choice(accounts)
                    bank_tx_id = self.ids.next("BTX")
                    sign = 1 if invoice["invoice_direction"] == "AR" else -1
                    self.writer.write("bank_transaction", {
                        "bank_transaction_id": bank_tx_id,
                        "bank_account_id": account["bank_account_id"],
                        "client_id": client["client_id"],
                        "transaction_date": d(paid_date),
                        "value_date": d(
                            paid_date + timedelta(days=self.rng.choice([0, 1]))
                        ),
                        "currency_code": account["currency_code"],
                        "transaction_amount": money(sign * paid_amount),
                        "transaction_amount_eur": money(sign * paid_amount),
                        "transaction_type": (
                            "CUSTOMER_PAYMENT"
                            if sign > 0
                            else "SUPPLIER_PAYMENT"
                        ),
                        "reference_text": invoice["invoice_number"],
                        "reconciliation_status": "MATCHED",
                    })
                    self.writer.write("reconciliation_match", {
                        "reconciliation_match_id": self.ids.next("REC"),
                        "bank_transaction_id": bank_tx_id,
                        "invoice_id": invoice["invoice_id"],
                        "matched_amount_eur": money(paid_amount),
                        "match_method": (
                            "AUTO"
                            if self.rng.random()
                            < float(
                                self.config["activity"][
                                    "automatic_reconciliation_probability"
                                ]
                            )
                            else "MANUAL"
                        ),
                        "match_confidence": round(
                            self.rng.uniform(0.91, 1.00), 4
                        ),
                        "matched_timestamp": dt(
                            random_datetime(self.rng, paid_date)
                        ),
                    })

                    if self.config["ledger"]["enabled"]:
                        entry_id = self.ids.next("JE")
                        self.writer.write("journal_entry", {
                            "journal_entry_id": entry_id,
                            "client_id": client["client_id"],
                            "entry_date": d(paid_date),
                            "accounting_period": paid_date.strftime("%Y-%m"),
                            "source_document_id": "",
                            "entry_type": "PAYMENT",
                            "description": "Payment posting",
                            "currency_code": "EUR",
                        })
                        lines = (
                            [
                                ("1000", paid_amount, 0),
                                ("1200", 0, paid_amount),
                            ]
                            if sign > 0
                            else [
                                ("1600", paid_amount, 0),
                                ("1000", 0, paid_amount),
                            ]
                        )
                        for account_code, debit, credit in lines:
                            self.writer.write("journal_line", {
                                "journal_line_id": self.ids.next("JL"),
                                "journal_entry_id": entry_id,
                                "gl_account_code": account_code,
                                "debit_amount_eur": money(debit),
                                "credit_amount_eur": money(credit),
                                "cost_center_code": f"CC-{client['industry_code']}",
                            })

                waiting_days = 0
                if late_documents:
                    waiting_days = max(
                        (
                            date.fromisoformat(
                                document["received_timestamp"][:10]
                            )
                            - date.fromisoformat(document["document_date"])
                        ).days
                        for document in late_documents
                    )
                    request_id = self.ids.next("DRQ")
                    request_date = month_end(month) - timedelta(days=6)
                    response_date = request_date + timedelta(
                        days=min(25, max(2, waiting_days))
                    )
                    self.writer.write("document_request", {
                        "document_request_id": request_id,
                        "client_id": client["client_id"],
                        "accountant_id": assignment["accountant_id"],
                        "request_date": d(request_date),
                        "due_date": d(request_date + timedelta(days=5)),
                        "response_date": d(response_date),
                        "requested_item_count": len(late_documents),
                        "received_item_count": len(late_documents),
                        "reminder_count": 2 if waiting_days > 10 else 1,
                        "status": "COMPLETED",
                        "completeness_pct": 100,
                    })
                    events = [
                        ("DOCUMENT_REQUEST", 0, "ACCOUNTING_FIRM"),
                        (
                            "AUTOMATED_REMINDER",
                            int(self.config["workflow"]["reminder_after_days"]),
                            "ACCOUNTING_FIRM",
                        ),
                        (
                            "CLIENT_RESPONSE",
                            min(25, max(2, waiting_days)),
                            "CLIENT",
                        ),
                    ]
                    for event_type, offset, sender in events:
                        event_date = request_date + timedelta(days=offset)
                        self.writer.write("communication_event", {
                            "communication_event_id": self.ids.next("COM"),
                            "client_id": client["client_id"],
                            "employee_id": assignment["accountant_id"],
                            "document_request_id": request_id,
                            "event_timestamp": dt(
                                random_datetime(self.rng, event_date)
                            ),
                            "channel": (
                                "PORTAL"
                                if client["digital_maturity"] == "HIGH"
                                else "EMAIL"
                            ),
                            "event_type": event_type,
                            "sender_side": sender,
                            "topic": "Missing accounting documents",
                            "urgency": (
                                "HIGH" if waiting_days > 10 else "NORMAL"
                            ),
                            "response_sla_hours": (
                                self.config["workflow"][
                                    "priority_response_sla_hours"
                                ]
                                if contract["sla_tier"] != "STANDARD"
                                else self.config["workflow"][
                                    "standard_response_sla_hours"
                                ]
                            ),
                        })

                task_codes = ["BOOKKEEP", "BANK_REC", "MONTH_CLOSE"]
                if int(client["employee_count"]) > 1:
                    task_codes.append("PAYROLL")
                for task_code in task_codes:
                    created = month_end(month) - timedelta(days=10)
                    due_date = month_end(month) + timedelta(
                        days=8 if task_code == "MONTH_CLOSE" else 3
                    )
                    base_hours = {
                        "LOW": 2.5, "MEDIUM": 4.5,
                        "HIGH": 7.5, "VERY_HIGH": 12.0,
                    }[client["accounting_complexity"]]
                    task_factor = {
                        "BOOKKEEP": 1.0, "BANK_REC": 0.45,
                        "MONTH_CLOSE": 0.65, "PAYROLL": 0.50,
                    }[task_code]
                    estimated = (
                        base_hours * task_factor * workload_multiplier
                    )
                    blocked = bool(late_documents) and task_code in {
                        "BOOKKEEP", "MONTH_CLOSE"
                    }
                    completion_lag = self.rng.randint(-3, 4) + (
                        min(15, waiting_days) if blocked else 0
                    )
                    completed = due_date + timedelta(days=completion_lag)
                    actual = estimated * self.rng.uniform(0.85, 1.30) * (
                        1.25 if blocked else 1.0
                    )
                    rework = int(
                        weighted_choice(
                            self.rng,
                            self.config["workflow"][
                                "rework_distribution"
                            ],
                        )
                    )
                    self.writer.write("work_item", {
                        "work_item_id": self.ids.next("WRK"),
                        "client_id": client["client_id"],
                        "task_type_code": task_code,
                        "assigned_employee_id": assignment["accountant_id"],
                        "reviewer_employee_id": "",
                        "accounting_period": month.strftime("%Y-%m"),
                        "created_timestamp": dt(
                            random_datetime(self.rng, created)
                        ),
                        "due_timestamp": dt(
                            random_datetime(self.rng, due_date)
                        ),
                        "completed_timestamp": dt(
                            random_datetime(self.rng, completed)
                        ),
                        "estimated_hours": round(estimated, 2),
                        "actual_hours": round(actual, 2),
                        "priority": "HIGH" if blocked else "NORMAL",
                        "status": "COMPLETED",
                        "blocked_reason": (
                            "WAITING_FOR_CLIENT" if blocked else ""
                        ),
                        "rework_count": rework,
                        "on_time_flag": completed <= due_date,
                    })

                if (
                    month.month in {3, 6, 9, 12}
                    or self.rng.random()
                    < float(
                        self.config["activity"][
                            "vat_filing_monthly_probability"
                        ]
                    )
                ):
                    statutory = month_end(month) + timedelta(days=10)
                    internal = statutory - timedelta(days=3)
                    submitted = internal + timedelta(
                        days=min(12, max(-2, waiting_days - 4))
                    )
                    status = (
                        "SUBMITTED"
                        if submitted <= statutory
                        else "OVERDUE"
                    )
                    self.writer.write("tax_filing", {
                        "tax_filing_id": self.ids.next("TAX"),
                        "client_id": client["client_id"],
                        "filing_type": "VAT_RETURN",
                        "filing_period": month.strftime("%Y-%m"),
                        "statutory_deadline": d(statutory),
                        "internal_deadline": d(internal),
                        "prepared_date": d(
                            submitted - timedelta(days=2)
                        ),
                        "reviewed_date": d(
                            submitted - timedelta(days=1)
                        ),
                        "submitted_date": d(submitted),
                        "status": status,
                        "amendment_count": self.rng.choices(
                            [0, 1], weights=[0.96, 0.04], k=1
                        )[0],
                        "penalty_risk": (
                            "HIGH" if status == "OVERDUE" else "LOW"
                        ),
                    })

    def generate_firm_billing(self) -> None:
        for client_index, client in enumerate(self.clients, start=1):
            if client_index % self.progress_every_clients == 0:
                self.log(
                    f"generated practice billing for "
                    f"{client_index}/{len(self.clients)} clients"
                )
            contract = next(
                row for row in self.contracts
                if row["client_id"] == client["client_id"]
            )
            services = [
                row for row in self.contract_services
                if row["contract_id"] == contract["contract_id"]
            ]
            service_fee = sum(
                float(row["monthly_fee_eur"]) for row in services
            )
            for month in self.months:
                if date.fromisoformat(contract["start_date"]) > month_end(month):
                    continue
                if (
                    contract["end_date"]
                    and date.fromisoformat(contract["end_date"]) < month
                ):
                    continue
                issue_date = month_end(month)
                usage_fee = self.rng.uniform(0, service_fee * 0.18)
                gross = (
                    float(contract["monthly_base_fee_eur"])
                    + service_fee
                    + usage_fee
                ) * (1 - float(contract["discount_pct"]) / 100)
                firm_invoice_id = self.ids.next("FINV")
                self.writer.write("firm_invoice", {
                    "firm_invoice_id": firm_invoice_id,
                    "firm_id": client["firm_id"],
                    "client_id": client["client_id"],
                    "contract_id": contract["contract_id"],
                    "billing_period": month.strftime("%Y-%m"),
                    "issue_date": d(issue_date),
                    "due_date": d(issue_date + timedelta(days=14)),
                    "base_fee_eur": contract["monthly_base_fee_eur"],
                    "service_fee_eur": money(service_fee),
                    "usage_fee_eur": money(usage_fee),
                    "discount_pct": contract["discount_pct"],
                    "gross_amount_eur": money(gross),
                    "payment_status": "OPEN",
                })

                pay_probability = {
                    "LOW": 0.96, "MEDIUM": 0.90, "HIGH": 0.82
                }[client["risk_category"]]
                if self.rng.random() < pay_probability:
                    max_days = max(
                        3, round(35 * self.multiplier("payment_delay"))
                    )
                    paid_date = issue_date + timedelta(
                        days=self.rng.randint(3, max_days)
                    )
                    self.writer.write("firm_payment", {
                        "firm_payment_id": self.ids.next("FPAY"),
                        "firm_invoice_id": firm_invoice_id,
                        "client_id": client["client_id"],
                        "payment_date": d(paid_date),
                        "payment_amount_eur": money(gross),
                        "payment_method": "BANK_TRANSFER",
                        "days_after_due": max(
                            0,
                            (
                                paid_date
                                - (issue_date + timedelta(days=14))
                            ).days,
                        ),
                    })

    def record_dq(
        self,
        table_name: str,
        record_id: str,
        rule_code: str,
        description: str,
    ) -> None:
        self.dq_issues.append({
            "dq_issue_id": self.ids.next("DQ"),
            "table_name": table_name,
            "record_id": record_id,
            "rule_code": rule_code,
            "description": description,
            "expected_issue": True,
        })
        self.dq_rule_counts[rule_code] = (
            self.dq_rule_counts.get(rule_code, 0) + 1
        )

    def write_dq_manifest(self) -> None:
        if not self.dq_issues:
            self.writer.write("dq_issue_manifest", {
                "dq_issue_id": "NONE",
                "table_name": "",
                "record_id": "",
                "rule_code": "NO_INJECTED_ISSUES",
                "description": (
                    "Clean generation mode or no random issue selected."
                ),
                "expected_issue": False,
            })
        else:
            for issue in self.dq_issues:
                self.writer.write("dq_issue_manifest", issue)
