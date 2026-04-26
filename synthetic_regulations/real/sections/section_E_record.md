# TICO Texas Statistical Plan for Residential Risks (eff. 2026-01-01)
# Section E: Record Layout for Cancellation, Nonrenewal, and Declination Notices
# Source: TX_Statistical_Plan_Residential_Risks_2026.pdf, chars 99300-103489 of source text

Section E: 
Record Layout  
for Cancellation, Nonrenewal,  
and Declination Notices  
 
 
 
 
 
  


===== PAGE 78 =====

Section E: Record Layout for  
Cancellation, Nonrenewal, and Declination Notices 
75 
 
 
Columns 
Code 
Type or Description 
 
1 (SP) 
Stat Plan 
 
 
5 
Residential – Dwellings, Homeowners 
2–4 (NDT) 
Notification Date 
This is the date on which the notice providing the reasons 
for cancellation, nonrenewal, or declination was sent to 
the policyholder or applicant. 
 
2 
Month 
 
1–9 
January–September 
 
0 
October 
 
- 
November 
 
& 
December 
 
3–4 
Year 
 
 
* 
Last two digits of Year; for example, "17" for 2017 
5–6 (AT) 
Action Type 
 
80 
Cancellation 
 
81 
Nonrenewal 
 
82 
Declination 
 
7–11 
 
NAIC Company Number 
 
* 
Report the five-digit NAIC company number. 
 
12–14 (CNO) 
 
Company Number 
 
* 
Assigned by TICO 
 
 
 
 


===== PAGE 79 =====

Section E: Record Layout for  
Cancellation, Nonrenewal, and Declination Notices 
 
Columns 
Code 
Type or Description 
 
76 
 
15–16 (TOP) 
Type of Policy 
 
01 
Tenants 
 
02 
Condominium owners (Condo) 
 
03 
Owner-occupied homeowners (HO) 
 
04 
Dwelling 
 
05 
Mobile homeowners (MHO) 
 
06 
Private flood – Stand-alone Flood Policies on Residential 
Dwellings (primary coverage) 
 
17 (RSI) 
 
Reason Source Indicator 
Indicate whether at least one of the reasons for the action type 
relied in whole or in part on aerial imagery or other third-party 
information. 
 
0 
Reasons do not include use of aerial imagery and do not 
include use of other third-party information 
 
1 
Reasons include use of aerial imagery but do not include use 
of other third-party information 
 
2 
Reasons do not include use of aerial imagery but include use 
of other third-party information 
 
3 
Reasons include use of aerial imagery and include use of 
other third-party information 
 
18 (60D) 
 
60-Day Indicator 
Indicate if cancellation notice was sent during the first 60 days 
of the initial policy term.  
 
Y 
Cancellation notice sent within the first 60 days 
 
N 
Cancellation notice sent after the first 60 days 
 
0 
For action types other than cancellations, enter “0” (zero) 
 
19–23 (ZIP) 
 
ZIP Code 
 
* 
Code the five-digit ZIP code. 
 
24–29 (AED) 
 
Action Effective Date 
 
* 
This is the date the Action Type is effective. For declinations, 
report the Notification Date. For flat cancellations, report the 
effective date of the policy. For all other actions, report the date 
coverage ends. Use YYYYMM format. 
 
 


===== PAGE 80 =====

Section E: Record Layout for  
Cancellation, Nonrenewal, and Declination Notices 
 
Columns 
Code 
Type or Description 
 
77 
 
30-35 (NPC) 
 
Notified Policy Count 
 
* 
The number of policies or applications for which the given 
combination of notification date, action type, type of policy, 
reason source indicator, 60-day indicator, ZIP code, action 
effective date, and reason code list applies. Pad on the left with 
zeroes as needed to reach the full field width of 6. 
 
36-45 (RCL) 
 
Reason Code List 
 
 
Concatenate all letter codes that apply from the following list in 
alphabetical order.  Pad on the right with zeroes as needed to 
reach the full field width of 10. 
 
 
A 
Failure to pay premiums when due 
 
B 
Increase in hazard 
 
C 
Inspection report not accepted 
 
D 
Claims history 
 
E 
Exposure to loss – liability 
 
F 
Exposure to loss – wildfire 
 
G 
Exposure to loss – wind/hail/hurricane 
 
H 
Exposure to loss – insurer's concentration of risk 
 
J 
Insurer withdrawing from the market 
 
K 
Location of risk 
 
L 
Credit or insurance score 
 
M 
Condition of property – roof 
 
N 
Condition of property – tree overhang 
 
P 
Condition of property – insufficient defensible space 
 
Q 
Condition of property – maintenance/occupancy/vacancy 
 
R 
Condition of property – other 
 
S 
Value of home 
 
T 
Agent no longer appointed with insurer  
 
X 
Assumption Reinsurance (TWIA only) 
 
Y 
At insured's request 
 
Z 
Other, insurer's action 
 
 
 
46-70 
 
Skip 
 
 


===== PAGE 81 =====

Section F: Additional Instructions for  
 Cancellation, Nonrenewal, and Declination Notices 
78 
 
 
 
 
 
 
 
 
 
 
