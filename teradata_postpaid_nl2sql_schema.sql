/*
================================================================================
 Teradata SQL Schema File: Postpaid Base, Sales, Churn, and Monthly Revenue
 Purpose: Natural-language-to-SQL conversion support
 Database/Schema: DP_EDW_PPF

 Tables included:
   1. DP_EDW_PPF.F_RM_POSTPAID_BASE
      - Subscription lifecycle/base table. Each record represents a subscription
        product status period with start and end timestamps.

   2. DP_EDW_PPF.F_RM_PSD_SALES
      - Daily sales/service-order line table. Each record represents a sales order
        line for a mobile line/MSISDN.

   3. DP_EDW_PPF.AF_RET_GSM_CHURN
      - Daily churn/customer churn attributes table. Used to analyze churn by date,
        churn type, nationality, region, customer profile, value, payment, complaints,
        and engagement attributes.

   4. DP_EDW_PPF.F_RM_PS_MTHLY_REV
      - Monthly line revenue table. Used to analyze line revenue, average revenue,
        value brackets, usage revenue, device revenue, discounts, and billing metrics.

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
       F_RM_POSTPAID_BASE.PROD_KEY / ROOT_PROD_NAME
       F_RM_PSD_SALES.PROD_KEY / PROD_NME / PROD_DESC
       AF_RET_GSM_CHURN.PACKAGE_ANME / PACKAGE_DESC

 Date usage guidance:
   - Subscription period: SUBS_STRT_DTTM, SUBS_END_DTTM,
     SUBS_PROD_STS_STRT_DTTM, SUBS_PROD_STS_END_DTTM.
   - Sales date: ORDER_END_DT.
   - Churn date: CHURN_DATE. Load snapshot date: LOAD_DATE.
   - Monthly revenue reference/billing dates: REF_DATE, BILL_STRT_DT.

 NL-to-SQL guidance:
   - For active base/subscription questions, use F_RM_POSTPAID_BASE and filter
     date ranges using SUBS_PROD_STS_STRT_DTTM and SUBS_PROD_STS_END_DTTM.
   - For sales questions, use F_RM_PSD_SALES and aggregate by ORDER_END_DT,
     ORDER_CHANNEL_NME, REGION, PROD_NME, SALES_CHNL_TYP, SUB_CHNL_NME, etc.
   - For churn questions, use AF_RET_GSM_CHURN and aggregate by CHURN_DATE,
     CHURN_TYPE, NATIONALITY, SAUDI_FLAG, REGION, CITY, VALUE_SEGMENT_NAME, etc.
   - For revenue questions, use F_RM_PS_MTHLY_REV and aggregate by REF_DATE,
     ACCS_METH_NUM, ACCT_NUM, and revenue fields such as TOTAL_LINE_REV,
     PACKAGE_REV, DEVICE_REV, USAGE_REV, and AVG_LINE_REV_LAST_3M.
================================================================================
*/

/* ============================================================================
   Table 1: Postpaid Base
   Business meaning:
     Every row indicates the start and end date/time for each subscription/product
     status period. Use this table for base size, active subscriptions, subscription
     status, subscription reason, product, account, and customer-level base analysis.
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
     and customer demographics at order-line level.
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
     segment, and exclusion segments.
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
   Common SQL examples for NL-to-SQL systems
============================================================================ */

/* Example: daily sales count by region */
/*
SELECT
    ORDER_END_DT,
    REGION,
    COUNT(*) AS SALES_LINE_COUNT
FROM DP_EDW_PPF.F_RM_PSD_SALES
GROUP BY 1, 2;
*/

/* Example: daily churn count by churn type and nationality */
/*
SELECT
    CHURN_DATE,
    CHURN_TYPE,
    NATIONALITY,
    COUNT(DISTINCT MSISDN) AS CHURNED_LINES
FROM DP_EDW_PPF.AF_RET_GSM_CHURN
GROUP BY 1, 2, 3;
*/

/* Example: monthly total revenue by reference month */
/*
SELECT
    REF_DATE,
    SUM(TOTAL_LINE_REV) AS TOTAL_REVENUE,
    AVG(AVG_LINE_REV_LAST_3M) AS AVG_REVENUE_LAST_3M
FROM DP_EDW_PPF.F_RM_PS_MTHLY_REV
GROUP BY 1;
*/

/* Example: active subscription base as of a selected date */
/*
SELECT
    COUNT(DISTINCT ACCS_METH_VAL) AS ACTIVE_LINES
FROM DP_EDW_PPF.F_RM_POSTPAID_BASE
WHERE TIMESTAMP '2026-01-31 00:00:00' BETWEEN SUBS_PROD_STS_STRT_DTTM
                                          AND COALESCE(SUBS_PROD_STS_END_DTTM, TIMESTAMP '9999-12-31 23:59:59');
*/

/* Example: revenue joined to churn by line number */
/*
SELECT
    c.CHURN_DATE,
    c.CHURN_TYPE,
    c.NATIONALITY,
    SUM(r.TOTAL_LINE_REV) AS TOTAL_LINE_REV_BEFORE_CHURN
FROM DP_EDW_PPF.AF_RET_GSM_CHURN c
LEFT JOIN DP_EDW_PPF.F_RM_PS_MTHLY_REV r
  ON c.MSISDN = r.ACCS_METH_NUM
GROUP BY 1, 2, 3;
*/
