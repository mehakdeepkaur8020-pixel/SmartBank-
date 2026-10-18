import io
import csv
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.models.models import Transaction, Loan, Account, Customer, AuditLog, AccountApplication
from app.utils.security import cents_to_currency, mask_account_number
from app.config import settings

def generate_transactions_csv(transactions: List[Transaction], account_num: Optional[str] = None) -> str:
    """Generate CSV string of transactions."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reference", "Date", "Type", "Source Account", "Destination Account",
        "Amount (INR)", "Balance After (INR)", "Status", "Description"
    ])

    for t in transactions:
        src = t.source_account.account_number if t.source_account else "N/A (External/Deposit)"
        dst = t.destination_account.account_number if t.destination_account else "N/A (Cash/Withdrawal)"
        writer.writerow([
            t.transaction_reference,
            t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            t.transaction_type,
            src,
            dst,
            cents_to_currency(t.amount_cents),
            cents_to_currency(t.balance_after_cents) if t.balance_after_cents is not None else "N/A",
            t.status,
            t.description
        ])

    return output.getvalue()

def generate_loans_csv(loans: List[Loan]) -> str:
    """Generate CSV string of loans."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Loan Reference", "Customer Name", "Category", "Requested Amount (INR)",
        "Approved Amount (INR)", "Outstanding Balance (INR)", "Term (Months)", "Status", "Applied Date"
    ])

    for l in loans:
        cust_name = l.customer.full_name if l.customer else "N/A"
        writer.writerow([
            l.loan_reference,
            cust_name,
            l.category,
            cents_to_currency(l.amount_cents),
            cents_to_currency(l.approved_amount_cents),
            cents_to_currency(l.outstanding_balance_cents),
            l.term_months,
            l.status,
            l.created_at.strftime("%Y-%m-%d")
        ])

    return output.getvalue()

def generate_accounts_csv(accounts: List[Account]) -> str:
    """Generate CSV string of customer accounts."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Account Number", "Customer Name", "Account Type", "Balance (INR)", "Status", "Currency", "Created Date"
    ])
    for acc in accounts:
        cust_name = acc.customer.full_name if acc.customer else "N/A"
        writer.writerow([
            acc.account_number,
            cust_name,
            acc.account_type,
            cents_to_currency(acc.balance_cents),
            acc.status,
            acc.currency,
            acc.created_at.strftime("%Y-%m-%d")
        ])
    return output.getvalue()

def generate_statement_pdf(
    account: Account,
    customer: Customer,
    transactions: List[Transaction],
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None
) -> bytes:
    """Generate a clean, professional bank account statement in PDF format using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b')
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0f172a')
    )
    normal_style = styles['Normal']

    elements = []

    # Bank Header with Midnight Navy and Emerald accent
    elements.append(Paragraph("<b>SmartBank Digital Financial Services</b>", title_style))
    elements.append(Paragraph(f"Official Statement of Account | Generated on {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} IST", subtitle_style))
    elements.append(Spacer(1, 15))

    # Account and Customer Details Table
    date_range_str = "All Time"
    if start_date and end_date:
        date_range_str = f"{start_date} to {end_date}"
    elif start_date:
        date_range_str = f"From {start_date}"
    elif end_date:
        date_range_str = f"Until {end_date}"

    masked_acc_no = mask_account_number(account.account_number)

    details_data = [
        [
            Paragraph("<b>Account Holder:</b> " + customer.full_name, normal_style),
            Paragraph("<b>Account Number:</b> " + masked_acc_no, normal_style)
        ],
        [
            Paragraph("<b>Email:</b> " + (customer.user.email if customer.user else "N/A"), normal_style),
            Paragraph("<b>Account Type:</b> " + account.account_type, normal_style)
        ],
        [
            Paragraph("<b>Contact:</b> " + customer.phone, normal_style),
            Paragraph("<b>Account Status:</b> " + account.status, normal_style)
        ],
        [
            Paragraph("<b>Statement Period:</b> " + date_range_str, normal_style),
            Paragraph("<b>Available Balance:</b> " + cents_to_currency(account.balance_cents), normal_style)
        ]
    ]

    details_table = Table(details_data, colWidths=[270, 270])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 20))

    # Transactions Header
    elements.append(Paragraph("Transaction Activity", section_style))
    elements.append(Spacer(1, 8))

    # Transaction Table
    if not transactions:
        elements.append(Paragraph("<i>No transactions found for the specified period.</i>", normal_style))
    else:
        table_data = [
            ["Date", "Reference", "Type", "Description", "Amount", "Balance After"]
        ]
        for t in transactions:
            is_credit = (t.destination_account_id == account.id and t.transaction_type in ("DEPOSIT", "TRANSFER"))
            amt_prefix = "+" if is_credit else "-"
            amt_display = f"{amt_prefix}{cents_to_currency(t.amount_cents)}"
            table_data.append([
                t.created_at.strftime("%Y-%m-%d"),
                t.transaction_reference,
                t.transaction_type,
                t.description[:25] + ("..." if len(t.description) > 25 else ""),
                amt_display,
                cents_to_currency(t.balance_after_cents) if t.balance_after_cents is not None else "-"
            ])

        tx_table = Table(table_data, colWidths=[65, 95, 75, 145, 80, 80])
        tx_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (4, 0), (5, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(tx_table)

    elements.append(Spacer(1, 25))
    footer_text = "This is a computer-generated statement issued by SmartBank Core Banking System. Currency displayed in Indian Rupees (INR). For queries, contact support@smartbank.co.in."
    elements.append(Paragraph(f"<font size=7 color='#64748b'>{footer_text}</font>", normal_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def generate_employee_report_pdf(
    title: str,
    subtitle: str,
    summary_stats: Dict[str, str],
    headers: List[str],
    rows: List[List[str]],
    landscape_mode: bool = False
) -> bytes:
    """Generate an institutional executive report in PDF format for employee/staff review."""
    buffer = io.BytesIO()
    page_size = landscape(letter) if landscape_mode else letter
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'EmpDocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a')
    )
    subtitle_style = ParagraphStyle(
        'EmpDocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#64748b')
    )
    stat_label_style = ParagraphStyle(
        'StatLabel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#64748b')
    )
    stat_val_style = ParagraphStyle(
        'StatVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0f172a')
    )
    normal_style = styles['Normal']

    elements = []
    elements.append(Paragraph(f"<b>SmartBank Management Operations Report</b>", title_style))
    elements.append(Paragraph(f"{title} &bull; {subtitle} | Exported at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} IST", subtitle_style))
    elements.append(Spacer(1, 12))

    # Summary Statistics Callout Box
    if summary_stats:
        stat_cells = []
        for k, v in summary_stats.items():
            cell = [
                Paragraph(k, stat_label_style),
                Paragraph(f"<b>{v}</b>", stat_val_style)
            ]
            stat_cells.append(cell)

        # Lay out horizontally
        stat_table = Table([stat_cells], colWidths=[(550 if not landscape_mode else 730) // len(stat_cells)] * len(stat_cells))
        stat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(stat_table)
        elements.append(Spacer(1, 15))

    # Table of Records
    if not rows:
        elements.append(Paragraph("<i>No records found matching the specified report criteria.</i>", normal_style))
    else:
        table_data = [headers] + rows
        available_width = 730 if landscape_mode else 550
        col_w = available_width // len(headers)
        col_widths = [col_w] * len(headers)

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(table)

    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<font size=7 color='#94a3b8'>SmartBank Institutional Internal Report &bull; Strictly Confidential &bull; For Authorized Staff Only</font>", normal_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

