/*
================================================================================
 Teradata SQL Schema File: Postpaid Base, Sales, Churn, Monthly Revenue, and Product Lookup
 Purpose: Natural-language-to-SQL conversion support
 Database/Schema: DP_EDW_PPF

 Tables included:
   1. DP_EDW_PPF.F_RM_POSTPAID_BASE
      - Subscription lifecycle/base table. Each row is a subscription product
        status period, not one row per line. For monthly base, reduce to one row
        per month/access method/account before joining to other fact tables.

   2. DP_EDW_PPF.F_RM_PSD_SALES
      - Daily sales/service-order line table. Each row is a completed service
        order line for a mobile line/MSISDN. Use ORDER_END_DT for sales timing.

   3. DP_EDW_PPF.AF_RET_GSM_CHURN
      - Daily churn line/customer attribute table. Each row is a churn event or
        churn-state record for a line. Use CHURN_DATE for churn timing and keep
        one churn per requested line/grain when joining.

   4. DP_EDW_PPF.F_RM_PS_MTHLY_REV
      - Monthly postpaid line revenue table. Each row is already at monthly
        line/account grain by REF_DATE. Use it directly for monthly revenue
        totals, averages, value bands, usage revenue, device revenue, discounts,
        and billing metrics.

   5. DP_EDW_PPF.D_RM_PSD_PRODUCTS
      - Shared product lookup used to translate PROD_KEY into the CRM product
        name, CRM product ID, and product price used by acquisition ARPU.

   6. DP_EDW_PPF.CBU_WEEKS
      - Calendar helper table. Use CALENDAR_DATE only when building daily/monthly
        active-base snapshots across subscription status periods.

 Common join keys / semantic relationships:
   - Mobile line / access method number:
       F_RM_POSTPAID_BASE.ACCS_METH_VAL
       F_RM_PSD_SALES.ACCS_METH_VAL
       AF_RET_GSM_CHURN.MSISDN
       F_RM_PS_MTHLY_REV.ACCS_METH_NUM

   - Account number:
       F_RM_POSTPAID_BASE.ACCNT_NMBR
       F_RM_PSD_SALES.ACCNT_NMBR
       AF_RET_GSM_CHURN.ACCNT_NUM
       F_RM_PS_MTHLY_REV.ACCT_NUM

   - Customer key / customer identifier:
       F_RM_POSTPAID_BASE.CUST_KEY
       F_RM_PSD_SALES.CUST_KEY
       AF_RET_GSM_CHURN.PARTY_ID / CUST_NUM / CUST_IDENT_NUM

   - Product/package:
       F_RM_POSTPAID_BASE.PROD_KEY -> D_RM_PSD_PRODUCTS.PROD_KEY
       F_RM_PSD_SALES.PROD_KEY    -> D_RM_PSD_PRODUCTS.PROD_KEY
       D_RM_PSD_PRODUCTS.CRM_PROD_Name / CRM_PROD_ID / PROD_PRICE_AMT
       AF_RET_GSM_CHURN.PACKAGE_ANME / PACKAGE_DESC

 Date usage guidance:
   - Subscription period: SUBS_STRT_DTTM, SUBS_END_DTTM,
     SUBS_PROD_STS_STRT_DTTM, SUBS_PROD_STS_END_DTTM.
   - Sales date: ORDER_END_DT.
   - Churn date: CHURN_DATE. Load snapshot date: LOAD_DATE.
   - Calendar helper date: CBU_WEEKS.CALENDAR_DATE.
   - Monthly revenue reference/billing dates: REF_DATE, BILL_STRT_DT. REF_DATE
     is the revenue month reference date and appears as month-end in samples;
     BILL_STRT_DT can be the next billing-cycle start date and should not be
     used as the default month filter for revenue totals.

 Grain and join safety:
   - Always know the grain before joining. Revenue, sales, churn, and base can
     have different row counts for the same line/account.
   - When joining line-level facts and both keys exist, join by both access
     method/MSISDN and account number:
       base.ACCS_METH_VAL = sales.ACCS_METH_VAL / churn.MSISDN / revenue.ACCS_METH_NUM
       base.ACCNT_NMBR    = sales.ACCNT_NMBR    / churn.ACCNT_NUM / revenue.ACCT_NUM
   - Before joining F_RM_POSTPAID_BASE to another table for month-level analysis,
     reduce base to one row per Last_Day(CALENDAR_DATE), ACCS_METH_VAL,
     and ACCNT_NMBR using QUALIFY ROW_NUMBER.
   - Join D_RM_PSD_PRODUCTS to base or sales on PROD_KEY when the CRM product
     name, product ID, or product price is required. Ensure the lookup contributes
     at most one row per PROD_KEY before aggregating facts.
   - For a standalone month revenue question such as June 2026 revenue, query
     F_RM_PS_MTHLY_REV directly using REF_DATE = DATE '2026-06-30' or a bounded
     June range. Do not join to base just to calculate total monthly revenue.
   - Avoid open-ended revenue joins such as R.REF_DATE >= BASE.CALENDAR_DATE for
     standalone monthly revenue totals; that returns future months for each base
     row and can multiply the result.

 NL-to-SQL guidance:
   - For active base/subscription questions, use F_RM_POSTPAID_BASE and filter
     date ranges using SUBS_PROD_STS_STRT_DTTM and SUBS_PROD_STS_END_DTTM. For
     postpaid service lines, common filters are LINE_TYPE = 'PS',
     SCREEN_TYPE IN ('SS', 'LS'), and SUBS_PROD_STS_TYP_NM not in
     ('Inactive','DELETED FROM SOURCE','UNKNOWN').
   - For sales questions, use F_RM_PSD_SALES and aggregate by ORDER_END_DT,
     ORDER_CHANNEL_NME, REGION, SALES_CHNL_TYP, SUB_CHNL_NME, etc. Use
     D_RM_PSD_PRODUCTS.CRM_PROD_Name as the standard sales/base product or
     rate-plan name after joining on PROD_KEY.
   - For postpaid churn questions, use AF_RET_GSM_CHURN with STREAM_TYPE = 'PS'
     and aggregate by CHURN_DATE, CHURN_TYPE, NATIONALITY, SAUDI_FLAG, REGION,
     CITY, VALUE_SEGMENT_NAME, etc.
   - For revenue questions, use F_RM_PS_MTHLY_REV directly unless the user
     explicitly asks for a lifecycle/base/sales/churn relationship. Aggregate by
     REF_DATE, ACCS_METH_NUM, ACCT_NUM, value band, and revenue fields such as
     TOTAL_LINE_REV, LINE_REV_EXCL_DEVICES, PACKAGE_REV, DEVICE_REV, USAGE_REV,
     ROAM_REV, DCB_REV, OTHER_USAGE_REV, and AVG_LINE_REV_LAST_3M.
   - SCREEN_TYPE mappings are SS = small screen and LS = large screen. When the
     user does not name one, return both separately. Churn already contains
     SCREEN_TYPE; derive it for sales or revenue from a deduplicated base
     lifecycle using line + account and the applicable exact date/month link.
================================================================================
*/

/* ============================================================================
   Table 1: Postpaid Base
   Business meaning:
     Every row indicates the start and end date/time for each subscription/product
     status period. This table can contain multiple rows for the same access method
     and account across time, products, and status changes. Use this table for base
     size, active subscriptions, subscription status, subscription reason, product,
     account, and customer-level base analysis.

     For active postpaid service-line base, common filters are:
       LINE_TYPE = 'PS'
       SCREEN_TYPE IN ('SS', 'LS')
       SUBS_PROD_STS_TYP_NM NOT IN ('Inactive','DELETED FROM SOURCE','UNKNOWN')

     Status rollups commonly used by analysts:
       Outgoing Barred -> D1
       Service Blocked, Incoming Barred, Suspended -> D2
============================================================================ */

CREATE SET TABLE DP_EDW_PPF.F_RM_POSTPAID_BASE ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      ACCS_METH_VAL VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC,
      ACCNT_NMBR VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      CUST_KEY INTEGER,
      ROOT_SUBS_KEY DECIMAL(18,0),
      ROOT_PROD_NAME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LINE_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SCREEN_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SUBS_STRT_DTTM TIMESTAMP(6),
      SUBS_END_DTTM TIMESTAMP(6),
      SUBS_KEY DECIMAL(18,0),
      PROD_KEY INTEGER,
      SUBS_PROD_STS_TYP_NM VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SUBS_PROD_STS_RSN_NM VARCHAR(500) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SUBS_PROD_STS_STRT_DTTM TIMESTAMP(0),
      SUBS_PROD_STS_END_DTTM TIMESTAMP(0))
PRIMARY INDEX ( ACCS_METH_VAL ,ACCNT_NMBR ,PROD_KEY ,SUBS_PROD_STS_STRT_DTTM )
INDEX POSTPAID_BASE_IDX01 ( PROD_KEY )
INDEX POSTPAID_BASE_IDX02 ( ROOT_SUBS_KEY )
INDEX POSTPAID_BASE_IDX03 ( CUST_KEY )
INDEX POSTPAID_BASE_IDX04 ( SUBS_PROD_STS_RSN_NM );

/*
Column guide: DP_EDW_PPF.F_RM_POSTPAID_BASE
  ACCS_METH_VAL              : Access method value / line number. Commonly joinable to sales ACCS_METH_VAL, churn MSISDN, and revenue ACCS_METH_NUM.
  ACCNT_NMBR                 : Account number. Commonly joinable to sales ACCNT_NMBR, churn ACCNT_NUM, and revenue ACCT_NUM.
  CUST_KEY                   : Customer key.
  ROOT_SUBS_KEY              : Root subscription key.
  ROOT_PROD_NAME             : Root product/package name.
  LINE_TYPE                  : Line type code.
  SCREEN_TYPE                : Screen type code.
  SUBS_STRT_DTTM             : Subscription start timestamp.
  SUBS_END_DTTM              : Subscription end timestamp.
  SUBS_KEY                   : Subscription key.
  PROD_KEY                   : Product key.
  SUBS_PROD_STS_TYP_NM       : Subscription product status type name.
  SUBS_PROD_STS_RSN_NM       : Subscription product status reason name.
  SUBS_PROD_STS_STRT_DTTM    : Subscription product status start timestamp.
  SUBS_PROD_STS_END_DTTM     : Subscription product status end timestamp.
*/

/* ============================================================================
   Table 2: Daily Sales by Line
   Business meaning:
     Every row represents a daily service order/sales line item. Use this table
     for sales counts, product sales, order types, channels, sales users, regions,
     and customer demographics at order-line level. ORDER_END_DT is the sales
     completion date. Samples show prepaid-to-postpaid migrations as
     ORDER_TYP_NME = 'Migrate' and ORDER_SUBTYP_NME = 'PrepaidtoPostpaid'.
============================================================================ */

CREATE SET TABLE DP_EDW_PPF.F_RM_PSD_SALES ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      SERVICE_ORDER_NUM VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      ORDER_END_DT DATE FORMAT 'YY/MM/DD',
      MSISDN VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC,
      ACCS_METH_VAL VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC,
      ACCNT_NMBR VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      CUST_KEY INTEGER,
      CUST_TAMAYUZ_MMBRSHP_TYP VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      CUST_GENDER_CD VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CUST_NAT_CD VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      ORDER_CLS_NM VARCHAR(22) CHARACTER SET UNICODE NOT CASESPECIFIC,
      ORDER_TYP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      ORDER_SUBTYP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SERVICE_ORDER_LINE_ITEM_RSN_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      PROD_KEY INTEGER,
      PROD_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      PROD_DESC VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CRTD_USR_KEY INTEGER,
      OWNR_USR_KEY INTEGER,
      ORDER_CHANNEL_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      COMPANY_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      REGION VARCHAR(30) CHARACTER SET LATIN NOT CASESPECIFIC,
      SALES_CHNL_TYP VARCHAR(14) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SUB_CHNL_NME VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      USER_NAME VARCHAR(250) CHARACTER SET UNICODE NOT CASESPECIFIC)
PRIMARY INDEX ( SERVICE_ORDER_NUM );

/*
Column guide: DP_EDW_PPF.F_RM_PSD_SALES
  SERVICE_ORDER_NUM                 : Service order number. Primary index.
  ORDER_END_DT                      : Date when the order ended/completed. Main date for daily sales reporting.
  MSISDN                            : Mobile number / line number.
  ACCS_METH_VAL                     : Access method value / line number. Joinable to base ACCS_METH_VAL, churn MSISDN, revenue ACCS_METH_NUM.
  ACCNT_NMBR                        : Account number.
  CUST_KEY                          : Customer key.
  CUST_TAMAYUZ_MMBRSHP_TYP          : Tamayuz membership type.
  CUST_GENDER_CD                    : Customer gender code.
  CUST_NAT_CD                       : Customer nationality code.
  ORDER_CLS_NM                      : Order class name.
  ORDER_TYP_NME                     : Order type name.
  ORDER_SUBTYP_NME                  : Order subtype name.
  SERVICE_ORDER_LINE_ITEM_RSN_NME   : Service order line item reason name.
  PROD_KEY                          : Product key. Joinable to postpaid base PROD_KEY.
  PROD_NME                          : Product name.
  PROD_DESC                         : Product description.
  CRTD_USR_KEY                      : Created-by user key.
  OWNR_USR_KEY                      : Owner user key.
  ORDER_CHANNEL_NME                 : Sales/order channel name.
  COMPANY_NME                       : Company name.
  REGION                            : Sales region.
  SALES_CHNL_TYP                    : Sales channel type.
  SUB_CHNL_NME                      : Sub-channel name.
  USER_NAME                         : User/agent name.
*/

/* ============================================================================
   Table 3: GSM Churn
   Business meaning:
     Churn table at daily customer/line level. Use this table to calculate churned
     customers or churned lines by churn date, churn type, nationality, Saudi flag,
     package, tenure, region, payment behavior, engagement, complaints, value
     segment, and exclusion segments. Samples include both prepaid stream records
     such as STREAM_TYPE = 'PP' and postpaid/service records such as STREAM_TYPE = 'PS'.
     This application is scoped exclusively to postpaid performance. Every churn
     query must use STREAM_TYPE = 'PS'; never query STREAM_TYPE = 'PP'.
============================================================================ */

CREATE SET TABLE DP_EDW_PPF.AF_RET_GSM_CHURN ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      LOAD_DATE DATE FORMAT 'yyyy-mm-dd',
      CHURN_DATE DATE FORMAT 'yyyy-mm-dd',
      DORMANCY_START_DATE DATE FORMAT 'yyyy-mm-dd',
      MSISDN VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC,
      ACCS_METH_ID DECIMAL(18,0),
      ACCNT_ID INTEGER,
      ACCNT_NUM VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      PARTY_ID INTEGER,
      CUST_NUM VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CUST_IDENT_NUM VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SUBS_ID DECIMAL(18,0),
      STREAM_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SCREEN_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CHURN_TYPE VARCHAR(61) CHARACTER SET UNICODE NOT CASESPECIFIC,
      PACKAGE_ANME CHAR(75) CHARACTER SET UNICODE NOT CASESPECIFIC,
      PACKAGE_DESC CHAR(75) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LINE_SUBS_DATE DATE FORMAT 'yyyy-mm-dd',
      GENDER VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      NATIONALITY VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SAUDI_FLAG VARCHAR(5) CHARACTER SET UNICODE NOT CASESPECIFIC,
      BIRTH_DATE VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      AGE_BRACKET CHAR(5) CHARACTER SET UNICODE NOT CASESPECIFIC,
      P_SEGMENT VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC,
      TAMAYUZ_TYPE VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      AGENT_ID VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LINE_TENURE INTEGER,
      CHURN_CHANNEL_NAME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC FORMAT 'X(2)',
      BLACKLIST_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      ZIYARAH_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LAST_ACTIVITY_DATE DATE FORMAT 'yyyy-mm-dd',
      LAST_ACTIVITY_NAME VARCHAR(8) CHARACTER SET UNICODE NOT CASESPECIFIC,
      USAGE_LIFETIME_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      ACCESS_DAYS_TIER VARCHAR(5) CHARACTER SET UNICODE NOT CASESPECIFIC,
      REGION VARCHAR(14) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CITY VARCHAR(32) CHARACTER SET LATIN NOT CASESPECIFIC,
      AREA VARCHAR(32) CHARACTER SET LATIN NOT CASESPECIFIC,
      VALUE_SEGMENT_NAME VARCHAR(11) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LAST_3M_AVG_REV DECIMAL(38,6),
      LAST_BILL_AMOUNT DECIMAL(18,4),
      LAST_DUE_AMOUNT DECIMAL(18,4),
      PAYMENT_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LAST_PAYMENT_AMOUNT DECIMAL(18,4),
      LAST_PAYMENT_DATE DATE FORMAT 'yyyy-mm-dd',
      LAST_BALANCE_AMOUNT DECIMAL(18,6),
      MIN_BILL_AMOUNT DECIMAL(18,4),
      MAX_BILL_AMOUNT DECIMAL(18,4),
      ENGAGED_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      COMPLAINT_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      NO_OF_COMPLAINTS INTEGER,
      COMPLAINT_TIER VARCHAR(5) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LAST_COMPLAINT_TYPE VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LAST_COMPLAINT_SUBTYPE VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC,
      POINTS_REDEMPTION_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      REDEMPTION_LAST_DATE DATE FORMAT 'yyyy-mm-dd',
      MOST_USED_REDEMPTION_DESTINATION VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC,
      MULTISIM_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC,
      EXCLUSION_SEGMENT CHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      EXCLUSION_SEGMENT_2 CHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC)
PRIMARY INDEX ( MSISDN );

/*
Column guide: DP_EDW_PPF.AF_RET_GSM_CHURN
  LOAD_DATE                         : Data load/snapshot date.
  CHURN_DATE                        : Main date for churn reporting and daily churn aggregation.
  DORMANCY_START_DATE               : Date dormancy started.
  MSISDN                            : Mobile number / line number. Primary index. Joinable to base ACCS_METH_VAL, sales ACCS_METH_VAL/MSISDN, revenue ACCS_METH_NUM.
  ACCS_METH_ID                      : Access method identifier.
  ACCNT_ID                          : Account identifier.
  ACCNT_NUM                         : Account number. Joinable to base ACCNT_NMBR, sales ACCNT_NMBR, revenue ACCT_NUM.
  PARTY_ID                          : Party/customer identifier.
  CUST_NUM                          : Customer number.
  CUST_IDENT_NUM                    : Customer identification number.
  SUBS_ID                           : Subscription identifier.
  STREAM_TYPE                       : Stream type code.
  SCREEN_TYPE                       : Screen type code.
  CHURN_TYPE                        : Churn type/category.
  PACKAGE_ANME                      : Package name.
  PACKAGE_DESC                      : Package description.
  LINE_SUBS_DATE                    : Line subscription date.
  GENDER                            : Customer gender.
  NATIONALITY                       : Customer nationality.
  SAUDI_FLAG                        : Saudi/non-Saudi indicator.
  BIRTH_DATE                        : Customer birth date stored as text.
  AGE_BRACKET                       : Customer age bracket.
  P_SEGMENT                         : Customer/product segment code.
  TAMAYUZ_TYPE                      : Tamayuz type.
  AGENT_ID                          : Agent identifier.
  LINE_TENURE                       : Tenure of the line.
  CHURN_CHANNEL_NAME                : Churn channel name.
  BLACKLIST_FLAG                    : Blacklist indicator.
  ZIYARAH_FLAG                      : Ziyarah indicator.
  LAST_ACTIVITY_DATE                : Last customer/line activity date.
  LAST_ACTIVITY_NAME                : Last activity name.
  USAGE_LIFETIME_FLAG               : Usage lifetime indicator.
  ACCESS_DAYS_TIER                  : Access days tier.
  REGION                            : Customer/line region.
  CITY                              : City.
  AREA                              : Area.
  VALUE_SEGMENT_NAME                : Value segment name.
  LAST_3M_AVG_REV                   : Average revenue over the last 3 months.
  LAST_BILL_AMOUNT                  : Last bill amount.
  LAST_DUE_AMOUNT                   : Last due amount.
  PAYMENT_FLAG                      : Payment indicator.
  LAST_PAYMENT_AMOUNT               : Last payment amount.
  LAST_PAYMENT_DATE                 : Last payment date.
  LAST_BALANCE_AMOUNT               : Last balance amount.
  MIN_BILL_AMOUNT                   : Minimum bill amount.
  MAX_BILL_AMOUNT                   : Maximum bill amount.
  ENGAGED_FLAG                      : Engagement indicator.
  COMPLAINT_FLAG                    : Complaint indicator.
  NO_OF_COMPLAINTS                  : Number of complaints.
  COMPLAINT_TIER                    : Complaint tier.
  LAST_COMPLAINT_TYPE               : Last complaint type.
  LAST_COMPLAINT_SUBTYPE            : Last complaint subtype.
  POINTS_REDEMPTION_FLAG            : Points redemption indicator.
  REDEMPTION_LAST_DATE              : Last redemption date.
  MOST_USED_REDEMPTION_DESTINATION  : Most used redemption destination.
  MULTISIM_FLAG                     : Multi-SIM indicator.
  EXCLUSION_SEGMENT                 : Exclusion segment.
  EXCLUSION_SEGMENT_2               : Secondary exclusion segment.
*/

/* ============================================================================
   Table 4: Monthly Postpaid Line Revenue
   Business meaning:
     Monthly line revenue table. Use this table for revenue, ARPU-like metrics,
     value brackets, device revenue, usage revenue, roaming revenue, DCB revenue,
     discounts, adjustments, number of lines, and last-3-month revenue metrics.
     REF_DATE is the revenue month reference and is month-end in the samples. For
     total revenue in a month, SUM(TOTAL_LINE_REV) directly from this table at
     that REF_DATE. For average revenue per line, use AVG(TOTAL_LINE_REV) or
     SUM(TOTAL_LINE_REV) / COUNT(DISTINCT ACCS_METH_NUM) depending on the
     requested business definition.
============================================================================ */

CREATE SET TABLE DP_EDW_PPF.F_RM_PS_MTHLY_REV ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      REF_DATE DATE FORMAT 'YY/MM/DD',
      Acct_Id INTEGER,
      ACCT_NUM VARCHAR(40) CHARACTER SET UNICODE CASESPECIFIC,
      Accs_Meth_Id DECIMAL(18,0),
      ACCS_METH_NUM VARCHAR(40) CHARACTER SET UNICODE CASESPECIFIC,
      PACKAGE_REV FLOAT,
      DEVICE_REV FLOAT,
      OTHER_SUBS_REV FLOAT,
      USAGE_REV FLOAT,
      TOTAL_LINE_REV FLOAT,
      LINE_REV_EXCL_DEVICES FLOAT,
      TOTAL_LINE_REV_LAST_3M FLOAT,
      AVG_LINE_REV_LAST_3M FLOAT,
      TOT_LINE_REV_EXCL_DEV_LAST_3M FLOAT,
      AVG_LINE_REV_EXCL_DEV_LAST_3M FLOAT,
      VBS_INCL_DEV VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      VBS_REV_BRACKET_INCL_DEV VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      VBS_EXCL_DEV VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      VBS_REV_BRACKET_EXCL_DEV VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      ROAM_REV FLOAT,
      DCB_REV FLOAT,
      OTHER_USAGE_REV FLOAT,
      DEVICE_DISC FLOAT,
      ROAM_DISC FLOAT,
      DCB_DISC FLOAT,
      OTHER_DISC FLOAT,
      ADJUSMENT FLOAT,
      NUMBER_OF_LINES INTEGER,
      BILL_STRT_DT DATE FORMAT 'YY/MM/DD',
      AVG_LINE_REV_EXCL_DEV_DCB_ROAM_LAST_3M FLOAT,
      Voucher_rev FLOAT)
PRIMARY INDEX ( REF_DATE ,Acct_Id ,Accs_Meth_Id );

/*
Column guide: DP_EDW_PPF.F_RM_PS_MTHLY_REV
  REF_DATE                                   : Monthly reference date. Main date for monthly revenue reporting.
  Acct_Id                                    : Account identifier.
  ACCT_NUM                                   : Account number. Joinable to base ACCNT_NMBR, sales ACCNT_NMBR, churn ACCNT_NUM.
  Accs_Meth_Id                               : Access method identifier.
  ACCS_METH_NUM                              : Access method number / line number. Joinable to base ACCS_METH_VAL, sales ACCS_METH_VAL/MSISDN, churn MSISDN.
  PACKAGE_REV                                : Package revenue.
  DEVICE_REV                                 : Device revenue.
  OTHER_SUBS_REV                             : Other subscription revenue.
  USAGE_REV                                  : Usage revenue.
  TOTAL_LINE_REV                             : Total line revenue including all revenue components.
  LINE_REV_EXCL_DEVICES                      : Line revenue excluding device revenue.
  TOTAL_LINE_REV_LAST_3M                     : Total line revenue over the last 3 months.
  AVG_LINE_REV_LAST_3M                       : Average line revenue over the last 3 months.
  TOT_LINE_REV_EXCL_DEV_LAST_3M              : Total line revenue excluding devices over the last 3 months.
  AVG_LINE_REV_EXCL_DEV_LAST_3M              : Average line revenue excluding devices over the last 3 months.
  VBS_INCL_DEV                               : Value band/segment including device revenue.
  VBS_REV_BRACKET_INCL_DEV                   : Revenue bracket including device revenue.
  VBS_EXCL_DEV                               : Value band/segment excluding device revenue.
  VBS_REV_BRACKET_EXCL_DEV                   : Revenue bracket excluding device revenue.
  ROAM_REV                                   : Roaming revenue.
  DCB_REV                                    : Direct carrier billing revenue.
  OTHER_USAGE_REV                            : Other usage revenue.
  DEVICE_DISC                                : Device discount.
  ROAM_DISC                                  : Roaming discount.
  DCB_DISC                                   : Direct carrier billing discount.
  OTHER_DISC                                 : Other discount.
  ADJUSMENT                                  : Adjustment amount. Column spelling is preserved from source DDL.
  NUMBER_OF_LINES                            : Number of lines.
  BILL_STRT_DT                               : Bill start date.
  AVG_LINE_REV_EXCL_DEV_DCB_ROAM_LAST_3M     : Average line revenue excluding device, DCB, and roaming over the last 3 months.
  Voucher_rev                                : Voucher revenue. Column casing is preserved from source DDL.
*/

/* ============================================================================
   Table 5: Product Lookup
   Business meaning:
     Shared product dimension for base and sales. The analyst-supplied contract
     confirms the columns below; source DDL types were not supplied, so no
     inferred CREATE TABLE statement is included here. Join through PROD_KEY.

Confirmed column contract: DP_EDW_PPF.D_RM_PSD_PRODUCTS
  PROD_KEY                    : Product key. Join to F_RM_POSTPAID_BASE.PROD_KEY or F_RM_PSD_SALES.PROD_KEY.
  CRM_PROD_Name               : Standard CRM product/rate-plan/package name for base and sales analysis.
  CRM_PROD_ID                 : CRM product/package identifier.
  PROD_PRICE_AMT              : Product price amount used for sales/acquisition ARPU.
============================================================================ */

/* ============================================================================
   Table 6: Calendar Helper
   Business meaning:
     Calendar/date helper used by analyst base snapshots. Use this only to expand
     subscription status periods into daily or month-end base dates. It is not a
     metric table.
============================================================================ */

CREATE SET TABLE DP_EDW_PPF.CBU_WEEKS ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO
     (
      CALENDAR_DATE DATE FORMAT 'YY/MM/DD');

/*
Column guide: DP_EDW_PPF.CBU_WEEKS
  CALENDAR_DATE                              : Calendar date used to build daily or monthly base snapshots.
*/

/* ============================================================================
   Common SQL examples for NL-to-SQL systems
============================================================================ */

/* Example: daily sales count by region for a bounded month */
/*
SELECT
    ORDER_END_DT,
    REGION,
    COUNT(*) AS SALES_LINE_COUNT
FROM DP_EDW_PPF.F_RM_PSD_SALES
WHERE ORDER_END_DT BETWEEN DATE '2026-06-01' AND DATE '2026-06-30'
GROUP BY 1, 2;
*/

/* Example: postpaid daily churn count by churn type and nationality for a bounded month */
/*
SELECT
    CHURN_DATE,
    CHURN_TYPE,
    NATIONALITY,
    COUNT(DISTINCT MSISDN) AS CHURNED_LINES
FROM DP_EDW_PPF.AF_RET_GSM_CHURN
WHERE CHURN_DATE BETWEEN DATE '2026-06-01' AND DATE '2026-06-30'
  AND STREAM_TYPE = 'PS'
  AND SCREEN_TYPE IN ('SS', 'LS')
GROUP BY 1, 2, 3;
*/

/* Example: standalone June 2026 total revenue; do not join to base for this */
/*
SELECT
    REF_DATE,
    SUM(TOTAL_LINE_REV) AS TOTAL_REVENUE,
    COUNT(DISTINCT ACCS_METH_NUM) AS UNIQUE_LINES
FROM DP_EDW_PPF.F_RM_PS_MTHLY_REV
WHERE REF_DATE = DATE '2026-06-30'
GROUP BY 1;
*/

/* Example: average June 2026 revenue per line by value segment */
/*
SELECT
    VBS_INCL_DEV,
    AVG(TOTAL_LINE_REV) AS AVG_REVENUE_PER_LINE,
    SUM(TOTAL_LINE_REV) AS TOTAL_REVENUE,
    COUNT(DISTINCT ACCS_METH_NUM) AS UNIQUE_LINES
FROM DP_EDW_PPF.F_RM_PS_MTHLY_REV
WHERE REF_DATE = DATE '2026-06-30'
GROUP BY 1;
*/

/* Example: active postpaid base at end of June 2026, deduped by line/account */
/*
SELECT
    BASE.CALENDAR_DATE,
    BASE.SCREEN_TYPE,
    BASE.ROOT_PROD_NAME,
    COUNT(DISTINCT BASE.ACCS_METH_VAL) AS ACTIVE_LINES
FROM
(
    SELECT
        LAST_DAY(W.CALENDAR_DATE) AS CALENDAR_DATE,
        PSB.ACCNT_NMBR,
        PSB.ACCS_METH_VAL,
        PSB.ROOT_PROD_NAME,
        PSB.SCREEN_TYPE,
        CAST(PSB.SUBS_STRT_DTTM AS DATE) AS LINE_STRT_DATE,
        CASE
            WHEN PSB.SUBS_PROD_STS_TYP_NM = 'Outgoing Barred' THEN 'D1'
            WHEN PSB.SUBS_PROD_STS_TYP_NM IN ('Service Blocked','Incoming Barred','Suspended') THEN 'D2'
            ELSE PSB.SUBS_PROD_STS_TYP_NM
        END AS SUBS_PROD_STS_TYP_NM
    FROM DP_EDW_PPF.F_RM_POSTPAID_BASE PSB
    INNER JOIN
    (
        SELECT CALENDAR_DATE
        FROM DP_EDW_PPF.CBU_WEEKS
        WHERE CALENDAR_DATE = DATE '2026-06-30'
        GROUP BY 1
    ) W
      ON W.CALENDAR_DATE BETWEEN CAST(PSB.SUBS_PROD_STS_STRT_DTTM AS DATE)
                             AND CAST(PSB.SUBS_PROD_STS_END_DTTM AS DATE)
    WHERE PSB.SUBS_PROD_STS_TYP_NM NOT IN ('Inactive','DELETED FROM SOURCE','UNKNOWN')
      AND PSB.LINE_TYPE = 'PS'
      AND PSB.SCREEN_TYPE IN ('SS', 'LS')
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY LAST_DAY(W.CALENDAR_DATE), PSB.ACCS_METH_VAL, PSB.ACCNT_NMBR
        ORDER BY PSB.SUBS_STRT_DTTM DESC,
                 PSB.SUBS_END_DTTM DESC,
                 PSB.SUBS_PROD_STS_STRT_DTTM DESC,
                 PSB.SUBS_PROD_STS_END_DTTM DESC
    ) = 1
) BASE
GROUP BY 1, 2, 3;
*/

/* Example: churn joined to same-month revenue at bounded grain */
/*
WITH CHURNED_LINES AS
(
    SELECT
        CHURN_DATE,
        MSISDN,
        ACCNT_NUM,
        CHURN_TYPE,
        CHURN_CHANNEL_NAME
    FROM DP_EDW_PPF.AF_RET_GSM_CHURN
    WHERE CHURN_DATE BETWEEN DATE '2026-06-01' AND DATE '2026-06-30'
      AND STREAM_TYPE = 'PS'
      AND SCREEN_TYPE IN ('SS', 'LS')
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY MSISDN, ACCNT_NUM
        ORDER BY CHURN_DATE
    ) = 1
),
JUNE_REVENUE AS
(
    SELECT
        ACCS_METH_NUM,
        ACCT_NUM,
        SUM(TOTAL_LINE_REV) AS TOTAL_LINE_REV
    FROM DP_EDW_PPF.F_RM_PS_MTHLY_REV
    WHERE REF_DATE = DATE '2026-06-30'
    GROUP BY 1, 2
)
SELECT
    C.CHURN_TYPE,
    C.CHURN_CHANNEL_NAME,
    COUNT(DISTINCT C.MSISDN) AS CHURNED_LINES,
    SUM(R.TOTAL_LINE_REV) AS JUNE_TOTAL_LINE_REV
FROM CHURNED_LINES C
LEFT JOIN JUNE_REVENUE R
  ON C.MSISDN = R.ACCS_METH_NUM
 AND C.ACCNT_NUM = R.ACCT_NUM
GROUP BY 1, 2;
*/
