# REPRODUCIBILITY REPORT - `full` dataset

_Rendered from `data/exports/full/reproducibility_report.json` (verified 2026-10-31T05:30:00)._

- **Result: IDENTICAL** - 2 independent regenerations from empty in-memory databases, **42 files** compared (CSV, JSON, SQL seed, validation report and ground truth).
- Seed: `20261022` | scale: `full` | anomalies: `True` | as-of date: `2026-10-22` | generator `1.0.0`
- Mismatches: none
- Software: {"generator_version": "1.0.0", "platform": "Linux", "premium_formula_version": "PREM-1.0.0", "python": "3.12.3", "rules_version": "RULES-1.0.0", "sqlalchemy": "2.1.6", "underwriting_engine_version": "UW-1.0.0"}

## What is (and is not) in the deterministic output

Deterministic: all dataset tables, IDs, timestamps (injected simulated clock), ground truth, validation report. NOT in checksums: `run_metadata.json` (wall-clock generation time), `dataset_runs` / `validation_runs` / `detected_exceptions` tables (run metadata).

How to reproduce: `cd backend && python -m app.data_generator --seed 20261022 --scale full --repro-check`

## SHA-256 checksums (run 1; run 2 identical)

| File | SHA-256 |
|---|---|
| [ground_truth] ground_truth/ground_truth.csv | `15f3687a07ebdd086f1546bf2a70a9150b9172637e4daf4c359b8fc1463d8f19` |
| [ground_truth] ground_truth/ground_truth.json | `11de6eb843d153ca00628e42bbd4eab57e18c75742ccbd416083f42f871b5d85` |
| csv/applicants.csv | `a6527734ffc28ec4d2ba87046ebbc8f98f4ad860371247348553a275ef567780` |
| csv/approval_authorities.csv | `b6a87c26449380a4baa157d05c3d46b01520163f4fce30d68d2323dd2c967640` |
| csv/audit_events.csv | `f90fea48e746b4ae081c8e4c28cca3e8fe78643408dcdb2154b66e0ab40fa109` |
| csv/coverage_options.csv | `fad1be04cfb286845bb1f81342627d071de9128f7f7415ccfdf265463764638c` |
| csv/endorsements.csv | `3e14a675c94543019f8295b2e4e5067e1a7156dbeffd9b5c5ba58689a6a26b59` |
| csv/id_counters.csv | `9fe067f0e5948ff32a84cac97e52cc03e9d09b91541f2f3959aac4bfc9970aec` |
| csv/insured_assets.csv | `b472cbcb50aa2c614d39d87f3f53a9c6d4f1a7a9fe4c71f716e323c6124d7435` |
| csv/payments.csv | `be522c674870a33fc5f589ba2d2db568c0998fb85b8621c6c13b2bbf55232c30` |
| csv/policies.csv | `2fc952bc852d6d71fdfde3663525b03ae02a6fddcda2e55276b1dea2429253b5` |
| csv/policy_coverages.csv | `12cf366217b8969f06fbe9d3401fa5bd00d2c5361f7b8e3a6d23daa96f2faa04` |
| csv/policy_status_history.csv | `2936468121328977886ef348c5b7b375082b9bd40e37144699d8cfb9f3eee7f0` |
| csv/product_coverages.csv | `c15ec51d9e928a403a851eadeb20a9835ce56b40db08b846fce9a6ab9aabf689` |
| csv/products.csv | `99993176369c60fde53ea03bfd4bd6a606343038290f3407ecaa5f31582971e4` |
| csv/quote_acceptances.csv | `439c6319c6afb505fe94771a8838a3d19b3ad2b40414b0f15cdeb56e4b4fb101` |
| csv/quote_coverages.csv | `f1bb6da511ac42d473b102cceb4fe83563152804aa7103271e10a0d09981be19` |
| csv/quotes.csv | `7de14c70d5d851c80f29e050180f74b4c5d1640968165ff35e4b5527cb85f3a9` |
| csv/renewals.csv | `f2ab1e84a33508a7df1d9aaaa5b3c1aff46e301870027814f9fa666919060bcd` |
| csv/risk_assessments.csv | `60dc9f9b3a00555350feb664d5e29260e0940457431b6ad307014c5efbd659d1` |
| csv/risk_factors.csv | `81eb6d023b461b0ae57cd6aa5f9e6f96b75b48746fbbd12f31a1aac63878dc47` |
| csv/underwriting_decisions.csv | `a33bd4b98385a7a9676757061f65f29fb7f63343c74ce315910447477e5b70ec` |
| json/applicants.json | `8368af13f52ba9004a5760bc6a88a176dcc1ca2cce98a58900d8301c3519e9d8` |
| json/approval_authorities.json | `c3d87e79bd38feed7df326a50ff894cbeb4d463a138d26755cc0e72b89472aad` |
| json/coverage_options.json | `d5e698c37d5cdcd0d3eb8f94ecfd2839b9f3229345522d4b50183dac52afe8b9` |
| json/endorsements.json | `1801d26bf8ae435ef0db187db361b96a31fa76fe7d48caf48a509d8af0525dd3` |
| json/id_counters.json | `61c0fdd642a60e08251fdc5ede84d53bbed3f3238db02cba31f36fddbb84b15a` |
| json/insured_assets.json | `a6ed323e20c5f8f334de2b0cc6a5959705e97d8797eb01b86ba4c0c80b8222da` |
| json/payments.json | `201a18befb209249bab20f17d238a702cdd49b3f865922d2f4ee00d5df922c2d` |
| json/policies.json | `5772bbc04f1b1a166f2b36596644a9910ce3f39badcc2fbbd02e862f284241cd` |
| json/policy_coverages.json | `6cff3859654d4df7814383aa7552d2d6ffdd970633d9d0015c772efe223c0ab3` |
| json/policy_status_history.json | `7385ba190694e3ad48cdb9c70b528ea64c3e7a3c66c77c69a21e66947801cdf1` |
| json/product_coverages.json | `447b84a8249ef9356fdd1a2d20d535906cb0000c7090fd52be252297f831c820` |
| json/products.json | `af237a6e0fab31260cdddcd37643b8ceb4b913c6f290d1949eb18ee24288deea` |
| json/quote_acceptances.json | `7f82726e9dad3ecdfcfeb08e5c6202e7e781a9409cfefbdfb0001c7c17100888` |
| json/quote_coverages.json | `2a67c8b603df502bcbbad1ad3217faa4f431acae424c84e340791356bba60f3f` |
| json/quotes.json | `77c152149cffa012a55284baf8a6661706a4df8a3cbbaeaad37ddfe2cfa81c22` |
| json/renewals.json | `e88787bae2df847e306bffd3345e733b7e739a37b1ef2a53db06dff0407e44e0` |
| json/risk_assessments.json | `4214975146472f8c26667650fc2927506237d0b7c715a28528d41bb56d21079d` |
| json/risk_factors.json | `2b78eab83df0e37eca9cfd6327925488329c374526af903f91bc237a476fee98` |
| seed_data.sql | `1ec2bbfc297037156187d78da00f2fb0db93bd00af64e7e455913a89544d1ae2` |
| validation_report.json | `b956bd2c9979032481594908d376eca8a3d327790580ffb0f5aa3324c12f9251` |
