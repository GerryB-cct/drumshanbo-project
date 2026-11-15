# Week 3 — AI Code Review
 
Reviewed by: Chatgpt    Date: Nov 14 2026
 
## Findings
 
1. predictable default secret key | anyone who knows the fallback can forge admin sessions 

2. test mode grants unauthenticated login to a known admin account | deliberate PoC feature

3. open redirects from unvalidated back form values| It needs a valid CSRF token, and the fix can wait.

4. exported CSV is vulnerable to spreadsheet formula injection |  A public applicant can put =... in their name or address and attack the librarian's Excel

5. no login or password-reset rate limiting | PoC feature.Needs hardening on production

6. cookies are not required to use HTTPS | only matters when on https

7. CSV upload processing reads the entire file and all rows into memory | 

8. uploaded CSV files remain indefinitely when the import is abandoned |

9. user-controlled email templates have no length limits | 

10. data-model constraints are mostly enforced only in application code | 
 
## What I fixed, and why
item 1.  refuse to start without SECRET_KEY when TEST_MODE is off.

item 4. prefix cells starting with = + - @ with ' before writing.
 
## What I am knowingly leaving, and why
notes on individual items above
 
## What the reviewer got wrong
item 9 has little relevance-only the librarian has access and would need to paste a huge doc by mistake.
