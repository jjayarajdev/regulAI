# TICO Stat Plan — Section D: Record Layout for Losses

*Field-by-field layout of loss records.*

---

Section D: Record Layout for Losses 

**Section D: Record Layout for Losses** 

58 

Section D: Record Layout for Losses 

|||Section D: Record Layout fo|
|---|---|---|
|**Columns**|**Code**|**Type or Description**|
|**1 (SP)**||**Stat Plan**|
||4|Residential – Dwellings, Homeowners|
|**2–4 (ACDT)**||**Accounting Date**|
|**2**||**Month**|
||1–9|January–September|
||0|October|
||-|November|
||&|December|
|**3–4**||**Year**|
||*|Last two digits of year, e.g., "15" for 2015|
|**5–6**||**Skip**|
|**7–16 (POLICY)**||**Policy Identifier**|
||*|Alphanumeric code assigned by the company to|
|||**uniquely**identify the policy for statistical reporting across|
|||all reporting periods.|
|**17–22**||**Loss Occurrence Date**|
||*|Date of Loss|
|||Report Month (2), Day (2), Year (2)|
|||MMDDYY|



59 

Section D: Record Layout for Losses 

## **Columns** 

## **Codes Type or Description** 

## **23–25 Policy Effective Date** 

- Report Month (2), Year (1) MMY 

## **26–30 (PLACE)** 

## **Place Code** 

- Place Code (County – Community) for specific location of risk as shown in the Place Code Manual. If risk is located in a specific community, report the Community Place Code. If risk is located outside a specific community, report the County Code. 

## **31 Kind** 

## **Records reporting no current payment or outstanding loss** 

- 1 

   - No loss amount, **not** previously reported as closed 

- 2 No loss amount, previously reported as **closed with payment** 3 No loss amount, previously reported as **closed** , but **never** as closed **with payment** 

- **Records reporting paid loss amount on reopened claims** 

- 4 Paid loss, previously reported as **closed with payment** 

- 5 Paid loss, previously reported as **closed** , but **never** as closed **with payment** 

## **Records reporting paid loss amount on claims not reopened** 

- 6 Paid loss, **not** previously reported as closed 

## **Records reporting outstanding loss amount** 

- 7 Outstanding loss, **not** previously reported as closed 

- 8 Outstanding loss, previously reported as **closed with payment** 9 Outstanding loss, previously reported as **closed** , but **never** as closed **with payment** 

## **Skip** 

**32** 

60 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **33–37 (A - INS) Amount of Insurance** 

* As per original premium coding. For specific codes refer to Premiums record layout section. 

If a previously reported loss record must be reversed, report this field as a credit of the previously reported value. See Rule 12 for instructions on coding negative quantities. 

## **38–40 Skip** 

## **41–42 (LOB) Line of Business** 

- 02 Homeowners Tenants Policies, including Condominium Owners 03 Homeowners Policies, Excluding Tenants and Condominium Forms 

- 10 Dwelling Policies – Fire – Property Damage and Time Element 11 Dwelling Policies – Miscellaneous Property Schedules 12 Dwelling Policies – Liability 13 Dwelling Policies – TWIA Wind-Only 14 Dwelling Policies – Voluntary Wind-Only (AR) 15 Dwelling Policies – Voluntary Wind-Only (Other) 16 Dwelling Policies – Theft 20 Dwelling Policies – Extended Coverage including Vandalism and Malicious Mischief – Property Damage and Time Element 

- 25 Dwelling Policies – Loss Assessment 26 Dwelling Policies – Additional Extended Coverage 27 Dwelling Policies – Residence Glass 28 Dwelling Policies – All Risk of Physical Loss 29 Dwelling Policies – Private Flood 35 Private Flood – Stand-alone Flood Policies on Residential Dwellings (primary coverage) 

- 50 Supplemental Natural Disaster Protection 

**43–45 (CO) Company Number** * As per original premium coding. For specific codes refer to Premiums record layout section. 

**46–49 Skip** 

**50 (F) Form** * As per original premium coding. For specific codes refer to Premiums record layout section. 

61 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **51 (FM) Number of Families** 

* As per original premium coding. For specific codes refer to Premiums record layout section. 

## **52 (CV) Coverage—Occupancy** 

* As per original premium coding. For specific codes refer to Premiums record layout section. 

## **53 (CT) Construction** 

* As per original premium coding. For specific codes refer to Premiums record layout section. 

## **54–55 Protection—ISO Protection Class, Including New Split (SPPC) Classifications** 

01 1 02 2 03 3 04 4 05 5 06 6 07 7 08 8 19 8B 09 9 10 10 20 10W 12 1X 22 2X 32 3X 42 4X 52 5X 62 6X 72 7X 82 8X 13 1Y 23 2Y 33 3Y 43 4Y 53 5Y 63 6Y 73 7Y 83 8Y 

62 

Section D: Record Layout for Losses 

- **Columns Codes Type or Description 56 (PPC) Protection—ISO Public Protection Class (PPC)** 1 2 3 4 Report actual ISO PPC used to rate the risk. 5 Report PPC = 10 as "A." 6 Report PPC = 8B as "B." 7 8 9 A B 

**57–58 (DED) Deductible** * As per original premium coding. For specific codes refer to Premiums record layout section. 

**59** 

- **Type of Loss Code HO** 

- 1 Losses – Section I (Dwelling) 1 Losses – Section I (Unscheduled Personal Property) 1 Losses – Section II (Personal Liability) 1 Losses – Section II (Medical Payments to Others) 

- 2 All Other Losses from additional premium paying endorsements 

- 3 All Losses Paid due to coverage added by attachment of Enhancement Endorsement 

**NOTE:** For watercraft losses covered under the basic policy (where total horsepower on outboard motors is less than or equal to 25 horsepower or sailboat is less than 26 feet in length), report "1." 

63 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **60 Paid Claim Count** 

- 1 The first payment record for a claim 

- 0 Nonpayment record (has a Kind Code not corresponding to a loss payment amount); or 

Payment record for a claim that has previously been reported with Paid Claim Count "1." 

- –1 Claim was previously reported in error as paid and needs to have all payments reversed; or 

Claim was previously reported with Paid Claim Count "1" and there has been salvage, subrogation, or other recoveries (not reinsurance) for the total cost of the case. 

See Rule 12 for instructions on coding negative quantities. 

A case involving a loss payment under several separate, differently coded statistical entries must include a single, separate record with Paid Claim Count "1" for each statistical entry. 

## **61–67** 

## **Amount of Loss** 

- Dollars only; indicate credit in units position. 

## **68–76** 

## **Nine-Digit ZIP Code** 

* The five-digit ZIP code of the location of the risk involved in the loss; report "ZIP code plus 4" if available. 

## **77–82** 

## **Skip** 

64 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **83 (ROOFCOV) Roof Covering (choose predominate type)** 

A Composition Shingle (Asphalt, Fiberglass, etc.) B Wood (Shingle, Shake, Hardboard, etc.) C Aluminum D Steel E Copper F Roll Roofing G Tar and Gravel (Built-up) H Tile (Concrete or Clay) I Slate J Fiber Cement/Concrete K Plastic L Recycled Roofing Products M Single-Ply Membrane Systems N Other O Metal (Specific type unknown) P Roof covering unknown and not used in rating 

## **84 (ROOFCRED)** 

## **Roof Covering Premium Credit** 

Report only premium credits for roof coverings meeting UL2218, or other standards approved by TDI, here. 0 None – No Credit Applicable 1 Class 1 Credit 2 Class 2 Credit 3 Class 3 Credit 4 Class 4 Credit 

## **85–88 (ROOFYEAR) Year of Roof Installation (HO and DW)** 

Report the year the roof was installed in YYYY format. If the insurer does not use year of roof installation in underwriting or rating, then report 0000. 

**89 (COSMETIC) Exclusion of Cosmetic Damage to Roof Coverings Endorsement** 0 Endorsement is not attached to policy 1 Endorsement is attached to policy 

65 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **90–91 Cause of Loss** 

- 05 Fire – Internal Source 10 Fire – External Source (Including fire caused by lightning) 15 Fire – Unknown Source 20 Lightning – No Fire 25 Windstorm 30 Hail 32 Flood or Rising Water 33 Explosion 35 Smoke 40 Aircraft and Vehicles 45 Riot and Civil Commotion 50 Vandalism and Malicious Mischief 55 Collapse 60 Discharge – Damage to Slab or Foundation 61 Discharge – Other Damage 70 Freeze – Damage to Slab or Foundation 71 Freeze – Other Damage 75 Burglary, Theft, Robbery 80 Other – Physical Damage 90 Other – Liability and Medical Payments 

## **92 Skip** 

**93–97 (DEPREC) Difference in Actual Cash Value and Replacement Cost** * Reportable only for loss on the roof. 

(Example: The replacement cost of a roof with a like product is $3,000. The Actual Cash Value of an existing roof is determined to be $2,500. Report the difference of $500 here.) 

**98–99 Skip 100** L **Loss Record 101–108** * **Optional Coverage Endorsements** (Report the actual endorsement number, excluding dashes, for example, HO161, HO162, TDP004, TDP005, etc., for endorsements providing coverage for mold, water, foundation, or flood.) 

## **109–114** * **Amount of Coverage for Field "101–108"** (Percent or dollar amount as applicable) 

If a previously reported loss record must be reversed, report this field as a credit of the previously reported value. See Rule 12 for instructions on coding negative quantities. 

## **115** 

**Skip** 

66 

Section D: Record Layout for Losses 

|||Section D: Record Layout for Lo|
|---|---|---|
|**Columns**|**Codes**|**Type or Description**|
|**116–121**|*|**Deductible 1 (HO – Wind and Hail; DW – Contents)**|
|||(Report actual dollar amount of the deductible.)|
|**122–127**|*|**Deductible 2 (HO – Other Than Wind and Hail; TN;**|
|||**DW – Building)**(Report actual dollar amount of the|
|||deductible.)|
|**128**||**Wind Coverage**|
||0|Wind Coverage is included.|
||1|Wind coverage is excluded.|
|**129–133**||**Skip**|
|**134–135 (BCC)**||**Building Code Credit (TWIA Only)**|
||01|Seaward – New Structure Built to New Code|
||02|Seaward – Retrofitted Structure|
||03|Inland I – New Structure Built to New Code|
||04|Inland I – New Structure Built to Higher Standard than New|
|||Code|
||05|Inland I – Retrofitted Structure|
|||Inland II – New Structure Built to Higher Standard than New|
|||Code:|
||06|Built to Inland I Standard|
||07|Built to Seaward Standard|
||08|Inland II – Retrofitted Structure|
||09|Not Applicable|
|**136 (LOC)**||**Law and Ordinance Coverage**|
||0|No Additional Law and Ordinance Coverage is attached|
|||(other than the amount provided in the policy)|
||1|10% Additional Law and Ordinance Coverage Purchased|
||2|15% Additional Law and Ordinance Coverage Purchased|
||3|25% Additional Law and Ordinance Coverage Purchased|
||4|Other Approved Limits Purchased|
|**137–139**||**Skip**|



67 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **140 Tenure Discount** 

Depending on whether the insurer uses tenure in rating or tiering, report the tenure of the insured using the following codes. Tenure is defined as the number of years previously insured with the insurer at the time the policy is issued or renewed. Insurers must report this code in all loss transactions, including those on policies that did not qualify for a tenurebased discount. Do not report tenure discounts elsewhere. 

   - 0 not used in rating or tiering 1 0–2 years 2 3–5 years 3 6–8 years 4 9–10 years 5 11–15 years 6 16–19 years 7 20 or more years 

- **141–142 Tenure Discount Amount** * Report the tenure discount amount. Report 10% as "10." Report no discount as "00." Do not report the tenure discount amount elsewhere. 

## **143–145 Skip** 

- **146–150 NAIC Company Number** * Report the five-digit NAIC company number. 

**151 (RCB) Replacement Cost Building (HO and DW)** 0 Policy provides actual cash value (ACV) coverage on the dwelling. 

   - 1 Policy provides replacement cost coverage on the dwelling. 2 Policy does not provide coverage for the dwelling. 

- **152 (RCPP) Replacement Cost Personal Property** 0 Policy provides actual cash value (ACV) coverage on personal property. 

- 1 Policy provides replacement cost coverage on personal property. 

   - 2 Policy does not provide coverage for personal property (DW Only). 

68 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

**153 (RCT) Roof Coverage Type** 0 Policy provides actual cash value (ACV) coverage on the roof (including policies that provide ACV coverage on the entire dwelling). 1 Policy provides actual cash value (ACV) coverage on the roof for the perils of windstorm or hail, but provides replacement cost coverage on the roof for other perils (such as fire). 2 Policy provides replacement cost coverage on the roof (including policies that provide replacement cost coverage on the entire dwelling). 3 Policy does not provide dwelling coverage. 4 Policy does not provide coverage for the roof, but provides dwelling coverage. 5 Policy does not provide coverage for the roof for the perils of windstorm and hail, but provides coverage for the roof for other perils. 

Policies that provide for fixed a schedule of payments for the roof that decline with the age of the home or the age of the roof must be reported using the codes that apply to actual cash value coverage. 

**154 Private Flood Coverage Indicator** 0 Policy does not provide any coverage for flood or rising waters and has not been endorsed to provide coverage for flood or rising waters. 1 Policy provides coverage for flood or rising waters, or has been endorsed to provide coverage for flood or rising water. 

69 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

**155 Tropical Cyclone Deductible (HO and Tenants, including Condominium Owners)** *1 Full Coverage 2 $100 3 $250 4 1/2% 5 1% 6 $500 **7 No Wind Coverage 8 $1,000 9 Greater than 10% A 1-1/2% B 2% C 2-1/2% D 3% E 4% F 5% G $1,500 H $2,000 I $2,500 J $3,000 K $4,000 L $5,000 M $750 N 10% O $3,500 P $7,500 Q $10,000 R 6% S 7% T 8% U 9% V $25,000 W $50,000 X $100,000 or greater Y $200 Z $15,000 

* For the Seacoast Territories (1, 8, 9, 10, and 11), code 1 is $100 Deductible on Wind, Hurricane, and Hail – Full Coverage on other Extended Coverage Perils. 

** Code 7 applies in Territories 8, 9, and 10, and those portions of La Porte, Morgan's Point, Pasadena, Seabrook, and Shore Acres in Territory 1 that are located in the Catastrophe Area, subject to Wind Exclusion Endorsement. 

70 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

- **156–161** 

## **Tropical Cyclone Deductible Amount (HO and Tenants, including Condominium Owners)** 

(Report actual dollar amount of the deductible applicable to tropical cyclones.) 

- **162–165 (YOC) Year of Construction (HO and DW)** 

Four-digit year the dwelling was constructed. Report "0000" for tenant forms and other contents-only policies. 

- **166–168 (ALE)** 

## **Amount of Insurance—Loss of Use Coverage (HO and DW)** 

Nearest thousands of dollars. If the amount of insurance is less than $1,500, then code "01." If loss of use limit is greater than $998,499, then report "999." 

If no loss of use coverage, then report "0" in the amount field. 

If a previously reported loss record must be reversed, report this field as a credit of the previously reported value. See Rule 12 for instructions on coding negative quantities. 

- **169–172 (HO PP)** 

## **Amount of Insurance—Personal Property Coverage (HO)** 

Homeowner policies only. For tenant and condo forms, report personal property limit under INS (pos. 33–37). 

Nearest thousands of dollars. If the amount of insurance is less than $1,500, then code "01." If personal property limit is greater than $9,998,499, report "9999." 

If a previously reported loss record must be reversed, report this field as a credit of the previously reported value. See Rule 12 for instructions on coding negative quantities. 

71 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **173 (NCC)** 

**New Claim Count** 

1 Newly reported claim 0 Previously reported as a newly reported claim –1 Reversal of previously reported new claim 

Claims previously reported, including in an earlier record for the current month, must use New Claim Count "0." 

New claims which were previously reported in error and need to be reversed must use New Claim Count "–1." 

See Rule 12 for instructions on coding negative quantities. 

## **174 (CS)** 

## **Claim Status** 

## **Claim open at the end of the month** 

- 1 Claim **open** , **not** previously reported as closed 4 Claim **open** , previously reported as **closed** 

**Claim closed with payment (CWIP) at the end of the month** 

   - claim closed at the end of the month; **and** 

   - one or more indemnity payments made to the insured and not recovered fully from the insured*,**. 

- 2 Claim **CWIP** , **not** previously reported as closed 5 Claim **CWIP** , previously reported as **closed** 

## **Claim closed without payment (CWOP) at the end of the month** 

   - claim closed at the end of the month; **and** 

   - indemnity payments made to the insured (if any) were all recovered fully from the insured*,**. 

- 3 Claim **CWOP** , **not** previously reported as closed 6 Claim **CWOP** , previously reported as **closed** 

* Indemnity payments made to the insured in the current month or in any earlier month are considered for the purpose of determining claim status. 

** Recoveries from any source other than the insured are not considered as amounts recovered for the purpose of determining claim status. 

72 

Section D: Record Layout for Losses 

## **Columns Codes Type or Description** 

## **175–176 (CLAIMID) Claim Identifier** 

* Alphanumeric code assigned by the company to identify the claim for statistical reporting across all reporting periods. For **multiple** claims reported on the **same** policy having the **same** occurrence date, each claim must have a **different** claim identifier. 

## **177 (RCC) Reopened Claim Count** 

- 1 Newly reopened claim, first loss record of the month 

- 0 Not a newly reopened claim; or Newly reopened claim, any record other than the first loss record of the month 

–1 Reversal of claim previously reported as newly reopened 

A claim is considered **"newly reopened"** in any month where the claim is being reported again after having last been reported as **closed** . 

See Rule 12 for instructions on coding negative quantities. 

## **178–200 Skip** 

73 

