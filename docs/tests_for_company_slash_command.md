| #  | Command / Scenario                                                                      | Expected Result                                                                       |
| -- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| 1  | `/company invest acronym:ZDB amount:0 note:test`                                        | 🚫 Invalid amount: 0. Must be greater than 0.                                         |
| 2  | `/company invest acronym:ZDB amount:-50 note:test`                                      | 🚫 Invalid amount: -50. Must be greater than 0.                                       |
| 3  | `/company invest acronym:ZDB amount:abc note:test`                                      | 🚫 Invalid amount: abc. Must be a number.                                             |
| 4  | `/company invest acronym:ZDB amount:100 note:test`                                      | ✅ Donation recorded under issuer’s Torn ID. Confirmation message sent.                |
| 5  | `/company invest acronym:ZDB amount:100 note:test delegate:@Uzumakikage` (allowed role) | ✅ Donation recorded under delegate’s Torn ID. Discord confirms on behalf of delegate. |
| 6  | `/company invest acronym:ZDB amount:100 note:test delegate:@SomeUser` (disallowed role) | 🚫 You cannot use this person as a delegate.                                          |
| 7  | `/company invest acronym:XYZ amount:100 note:test` (invalid company)                    | ⚠️ Invalid/unknown company                                                            |
| 8  | `/company return acronym:ZDB amount:0 note:test`                                        | 🚫 Invalid amount: 0. Must be greater than 0.                                         |
| 9  | `/company return acronym:ZDB amount:-50 note:test`                                      | 🚫 Invalid amount: -50. Must be greater than 0.                                       |
| 10 | `/company return acronym:ZDB amount:50 note:test`                                       | ✅ Return recorded under issuer’s Torn ID. Confirmation message sent.                  |
| 11 | `/company return acronym:ZDB amount:50 note:test delegate:@Uzumakikage` (allowed role)  | ✅ Return recorded under delegate’s Torn ID. Discord confirms on behalf of delegate.   |
| 12 | `/company return acronym:ZDB amount:50 note:test delegate:@SomeUser` (disallowed role)  | 🚫 You cannot use this person as a delegate.                                          |
| 13 | `/company return acronym:ZDB amount:50 note:test` (no previous investment)              | 🚫 No donation record found for ZDB under your ID. Cannot record return.              |
| 14 | `/company return acronym:XYZ amount:50 note:test` (invalid company)                     | ⚠️ Invalid/unknown company                                                            |
