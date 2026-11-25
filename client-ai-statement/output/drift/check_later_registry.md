# Drift check

Statement dated 2026-11-25 (version 1.0, DRAFT) checked against the registry dated 2027-05-20, as of 2027-05-20.

**RESULT: 2 printed sentence(s) are no longer backed by the registry. Withdraw or reissue the statement.**

## NO LONGER SUPPORTED

- "No tool we use allows what we enter to be used to train a model." (`no_training / all_tools`, section: How your information is protected)
  - transcript-summary: data_boundary.used_for_training must be 'no'; found 'yes'
- "We review tools every 180 days. Each tool in use has a review on record within that period." (`review_cycle / registry_interval`, section: How work is checked)
  - translation: last_review must be a date no more than 180 days before the as-of date; found '2026-09-30' (232 days before the as-of date 2027-05-20)

## STILL TRUE (12)

- `tools_in_use / by_category`
- `rollout / split`
- `named_owner / each`
- `uses / listed`
- `not_for_client_information / count`
- `no_sensitive_data / personal_and_health`
- `provider_agreements / each`
- `human_review / every`
- `testing / every_in_use`
- `court_citations / each`
- `client_terms_check / each_recent`
- `contact / role`

## NOT CHECKED (4)

These sentences are policy wording with no registry rule. The registry cannot confirm or contradict them.

- `confidentiality / C1`
- `court_disclosure / D1`
- `billing / B1`
- `opt_out / O1`

## Notes

- A rebuild would print claim 'no_training' as variant 'count' instead of 'all_tools'.
- A rebuild would print claim 'review_cycle' as variant 'annual' instead of 'registry_interval'.
