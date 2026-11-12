# Final Engineering Audit — T088 / PS-063

## Scope
This audit was performed against the supplied company sample-data pack and
the current Python source. It is not a guarantee of hidden-evaluation results.

## Corrections made in this pass
- Made hospital quota input optional for minimal unit-test fixtures while
  retaining enforcement when quota rows are supplied.
- Enforced routine quota reductions only for routine requests when the
  monthly replacement ratio exceeds 1.5; emergency requests bypass quotas.
- Released allocated units that exceed a hospital's daily issue quota and
  queued the unissued shortfall.
- Prevented routine allocation from consuming critical stock (<2 available).
- Added emergency PRBC immediate issue and retrospective cross-match tracking.
- Added routine reservation pre-emption for an emergency when no compatible
  available PRBC unit exists; a reservation exactly 72 hours old is released
  normally rather than treated as a pre-emption.
- Integrated platelet pooling for multi-unit requests: same ABO group and
  member expiries within 24 hours; pool expiry is the earliest member expiry.
- Corrected end-of-day expiry and reservation processing so all reservations
  are processed rather than returning after the first one.
- Corrected return billing so only eligible returns within 30 minutes with
  cold chain remove the matching invoice; late/broken-cold-chain returns stay
  billed and are discarded.
- Corrected command processing so the command stream is executed once and
  completion is reported after the entire stream.
- Added explicit shortfall rows to the allocation report.
- Added four regression tests for optional quota input, multiple reservation
  releases, quota-limited issue, and emergency retrospective cross-match.

## Verification performed
- `python -m pytest -q`: **118 passed**.
- `python -m src.main`: completed successfully against the supplied dataset.
- Processed **637 commands** in strict input order.
- Generated all five required CSV outputs.
- Output headers checked against the supplied column contract.
- Duplicate `(request_id, unit_id)` allocation rows: none in the generated run.
- Units with more than one active allocation: none in the generated run.

## Remaining evaluation caution
The company states that final evaluation uses a separate hidden dataset and
compares outputs field-for-field. The supplied pack has no expected-output
files, so exact hidden-output parity cannot be proven locally. Review the
company's final feedback if it specifies any additional tie-break or output
format detail. Run the test suite and sample command stream again after any
future code edits.
