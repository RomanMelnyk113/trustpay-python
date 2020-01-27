class PaymentException(Exception):
    pass


order_xml_string = '''
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:xsd="http://www.w3.org/2001/XMLSchema"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
    <CstmrCdtTrfInitn>
        <GrpHdr>
            <MsgId>{MessageId}</MsgId>
            <CreDtTm>{CreationDateTime}</CreDtTm>
            <NbOfTxs>1</NbOfTxs>
            <InitgPty/>
        </GrpHdr>
        <PmtInf>
            <PmtInfId>1</PmtInfId>
            <PmtMtd>TRF</PmtMtd>
            <PmtTpInf>
                <LclInstrm>
                    <Prtry>BWT2/EU</Prtry>
                </LclInstrm>
            </PmtTpInf>
            <ReqdExctnDt>{RequestedExecutionDate}</ReqdExctnDt>
            <Dbtr>
                <Nm>{DebtorName}</Nm>
            </Dbtr>
            <DbtrAcct>
                <Id>
                    <Othr>
                        <Id>{DebtorAccount}</Id>
                    </Othr>
                </Id>
            </DbtrAcct>
            <DbtrAgt>
                <FinInstnId>
                    <BIC>TPAYSKBX</BIC>
                </FinInstnId>
            </DbtrAgt>
            <CdtTrfTxInf>
                <PmtId>
                    <EndToEndId>NOTPROVIDED</EndToEndId>
                </PmtId>
                <PmtTpInf>
                    <LclInstrm>
                        <Cd>010000</Cd>
                    </LclInstrm>
                </PmtTpInf>
                <Amt>
                    <InstdAmt Ccy="{Currency}">{Amount}</InstdAmt>
                </Amt>
                <CdtrAgt>
                    <FinInstnId>
                        <BIC>{CreditorBankBic}</BIC>
                    </FinInstnId>
                </CdtrAgt>
                <Cdtr>
                    <Nm>{CreditorName}</Nm>
                </Cdtr>
                <CdtrAcct>
                    <Id>
                        <IBAN>{CreditorAccount}</IBAN>
                    </Id>
                </CdtrAcct>
                <RmtInf>
                    <Ustrd>{Description}</Ustrd>
                </RmtInf>
            </CdtTrfTxInf>
        </PmtInf>
    </CstmrCdtTrfInitn>
</Document>
'''