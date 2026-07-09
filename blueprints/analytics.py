"""
blueprints/analytics.py — analytics and PDF export routes.

Routes: /analytics, /export/pdf
Blueprint name: 'analytics'
Endpoint prefix: analytics.<function_name>
"""
import calendar as cal_module
import io
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import (
    Blueprint, render_template, request, redirect,
    session, flash, url_for, make_response,
)
from models import db, User, Expense
from utils import (
    is_logged_in, get_current_year_month, get_user_budget, get_budget_history,
)

logger = logging.getLogger('expenseflow')

analytics_bp = Blueprint('analytics', __name__)


# ── Analytics page ────────────────────────────────────────────────────────────

@analytics_bp.route('/analytics')
def analytics():
    """
    Spending analytics page with 9 sections:
    KPI cards, trend banner, category breakdown + table, MoM grouped bar,
    daily bar chart, payment method chart, top 5 expenses, calendar heatmap.
    Accepts ?month=YYYY-MM query param to switch months.
    """
    if not is_logged_in():
        flash('Please log in to access analytics.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))

    # ── Selected month (from query param or current) ──────────────────────
    selected_month = request.args.get('month', get_current_year_month())
    try:
        sel_dt = datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        sel_dt = datetime.now()
        selected_month = sel_dt.strftime("%Y-%m")

    prev_dt = sel_dt - relativedelta(months=1)
    prev_month = prev_dt.strftime("%Y-%m")

    # ── Fetch expenses ─────────────────────────────────────────────────────
    month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(selected_month)
    ).order_by(Expense.amount.desc()).all()

    prev_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(prev_month)
    ).all()

    all_expenses = Expense.query.filter_by(user_id=user_id).all()

    # ── Available months for selector ─────────────────────────────────────
    all_months_raw = sorted(set(e.date[:7] for e in all_expenses), reverse=True)
    available_months = [
        {'value': m, 'label': datetime.strptime(m, "%Y-%m").strftime("%B %Y")}
        for m in all_months_raw
    ]
    if not any(m['value'] == selected_month for m in available_months):
        available_months.insert(0, {
            'value': selected_month,
            'label': sel_dt.strftime("%B %Y")
        })

    # ── Basic totals ───────────────────────────────────────────────────────
    total_this_month = sum(e.amount for e in month_expenses)
    total_prev_month = sum(e.amount for e in prev_expenses)

    if total_prev_month > 0:
        mom_change_pct = ((total_this_month - total_prev_month) / total_prev_month) * 100
    else:
        mom_change_pct = 0.0
    mom_direction = 'up' if mom_change_pct > 0 else ('down' if mom_change_pct < 0 else 'flat')

    # ── Active days ────────────────────────────────────────────────────────
    active_days = len(set(e.date for e in month_expenses))

    # ── Biggest expense ────────────────────────────────────────────────────
    biggest_expense = month_expenses[0] if month_expenses else None

    # ── Daily totals (for bar chart + calendar) ────────────────────────────
    days_in_month = cal_module.monthrange(sel_dt.year, sel_dt.month)[1]
    daily_totals = {}
    for e in month_expenses:
        day = int(e.date[8:10])
        daily_totals[day] = daily_totals.get(day, 0) + e.amount

    daily_labels = list(range(1, days_in_month + 1))
    daily_amounts = [round(daily_totals.get(d, 0), 2) for d in daily_labels]
    peak_day = max(daily_totals, key=daily_totals.get) if daily_totals else None
    peak_day_amount = daily_totals.get(peak_day, 0) if peak_day else 0

    # ── Category breakdown ─────────────────────────────────────────────────
    cat_totals = {}
    for e in month_expenses:
        cat_totals[e.category] = cat_totals.get(e.category, 0) + e.amount
    cat_totals_sorted = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
    cat_labels = [c[0] for c in cat_totals_sorted]
    cat_amounts = [round(c[1], 2) for c in cat_totals_sorted]
    cat_percentages = [
        round((c[1] / total_this_month * 100), 1) if total_this_month > 0 else 0
        for c in cat_totals_sorted
    ]

    # ── Category MoM change (for trend banner) ─────────────────────────────
    prev_cat_totals = {}
    for e in prev_expenses:
        prev_cat_totals[e.category] = prev_cat_totals.get(e.category, 0) + e.amount

    cat_mom = {}
    for cat, amt in cat_totals.items():
        prev_amt = prev_cat_totals.get(cat, 0)
        cat_mom[cat] = amt - prev_amt
    biggest_increase_cat = max(cat_mom, key=cat_mom.get) if cat_mom else None
    biggest_increase_amt = cat_mom.get(biggest_increase_cat, 0) if biggest_increase_cat else 0

    # ── Payment method breakdown ───────────────────────────────────────────
    pay_totals = {}
    for e in month_expenses:
        method = e.payment_method or 'Other'
        pay_totals[method] = pay_totals.get(method, 0) + e.amount
    pay_totals_sorted = sorted(pay_totals.items(), key=lambda x: x[1], reverse=True)
    pay_labels = [p[0] for p in pay_totals_sorted]
    pay_amounts = [round(p[1], 2) for p in pay_totals_sorted]

    # ── Top 5 expenses ─────────────────────────────────────────────────────
    top_5 = month_expenses[:5]

    # ── Budget history for grouped bar (6 months) ──────────────────────────
    budget_history = get_budget_history(user_id, 6)
    bh_labels   = [item['month'] for item in reversed(budget_history)]
    bh_budgets  = [item['budget'] for item in reversed(budget_history)]
    bh_spending = [item['spending'] for item in reversed(budget_history)]

    # ── Calendar heatmap data ──────────────────────────────────────────────
    max_day_spend = max(daily_amounts) if daily_amounts else 1
    calendar_weeks = []
    first_weekday = cal_module.monthrange(sel_dt.year, sel_dt.month)[0]  # 0=Mon
    day_counter = 1
    week = [None] * first_weekday
    while day_counter <= days_in_month:
        week.append({
            'day': day_counter,
            'amount': daily_totals.get(day_counter, 0),
            'intensity': round(daily_totals.get(day_counter, 0) / max_day_spend, 2) if max_day_spend > 0 else 0
        })
        if len(week) == 7:
            calendar_weeks.append(week)
            week = []
        day_counter += 1
    if week:
        while len(week) < 7:
            week.append(None)
        calendar_weeks.append(week)

    # ── Avg daily spend ────────────────────────────────────────────────────
    avg_daily = total_this_month / days_in_month if days_in_month > 0 else 0

    return render_template('analytics.html',
        username=user.username,
        selected_month=selected_month,
        selected_month_label=sel_dt.strftime("%B %Y"),
        available_months=available_months,
        # Totals
        total_this_month=total_this_month,
        total_prev_month=total_prev_month,
        mom_change_pct=mom_change_pct,
        mom_direction=mom_direction,
        active_days=active_days,
        days_in_month=days_in_month,
        avg_daily=avg_daily,
        # Biggest
        biggest_expense=biggest_expense,
        peak_day=peak_day,
        peak_day_amount=peak_day_amount,
        # Top 5
        top_5=top_5,
        # Trend banner
        biggest_increase_cat=biggest_increase_cat,
        biggest_increase_amt=biggest_increase_amt,
        # Category chart
        cat_labels=cat_labels,
        cat_amounts=cat_amounts,
        cat_percentages=cat_percentages,
        cat_totals_sorted=cat_totals_sorted,
        # Daily chart
        daily_labels=daily_labels,
        daily_amounts=daily_amounts,
        # Payment chart
        pay_labels=pay_labels,
        pay_amounts=pay_amounts,
        # Budget history chart
        bh_labels=bh_labels,
        bh_budgets=bh_budgets,
        bh_spending=bh_spending,
        # Calendar
        calendar_weeks=calendar_weeks,
        sel_dt=sel_dt,
        current_date=datetime.now(),
    )


# ── PDF export ────────────────────────────────────────────────────────────────

@analytics_bp.route('/export/pdf')
def export_pdf():
    """
    Generate and stream a PDF expense report for the selected month.
    Uses ReportLab SimpleDocTemplate with Platypus for layout.
    Accepts ?month=YYYY-MM; defaults to current month.
    Returns the PDF as a file download attachment.
    """
    if not is_logged_in():
        flash('Please log in first.', 'error')
        return redirect(url_for('auth.login'))

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('auth.login'))

    # ── Month selection ──────────────────────────────────────────────────
    selected_month = request.args.get('month', get_current_year_month())
    try:
        sel_dt = datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        sel_dt = datetime.now()
        selected_month = sel_dt.strftime("%Y-%m")

    month_label = sel_dt.strftime("%B %Y")

    # ── Fetch data ───────────────────────────────────────────────────────
    month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(selected_month)
    ).order_by(Expense.date.desc()).all()

    all_expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()

    total_spent = sum(e.amount for e in month_expenses)
    budget = get_user_budget(user_id, selected_month)
    remaining = budget - total_spent

    cat_totals = {}
    for e in month_expenses:
        cat_totals[e.category] = cat_totals.get(e.category, 0) + e.amount
    cat_sorted = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)

    # ── Colours ──────────────────────────────────────────────────────────
    INDIGO      = colors.HexColor('#4F46E5')
    INDIGO_LIGHT= colors.HexColor('#EEF2FF')
    SLATE       = colors.HexColor('#64748B')
    DANGER      = colors.HexColor('#EF4444')
    SUCCESS     = colors.HexColor('#10B981')
    BLACK       = colors.HexColor('#1E293B')
    BORDER      = colors.HexColor('#E2E8F0')
    WHITE       = colors.white
    ROW_ALT     = colors.HexColor('#F8FAFC')

    # ── Styles ───────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()
    def style(name, **kw):
        s = ParagraphStyle(name, **kw)
        return s

    title_style   = style('Title2', fontName='Helvetica-Bold', fontSize=20, textColor=WHITE, alignment=TA_LEFT, spaceAfter=2)
    sub_style     = style('Sub',    fontName='Helvetica',      fontSize=9,  textColor=colors.HexColor('#CBD5E1'), alignment=TA_LEFT)
    section_style = style('Sec',    fontName='Helvetica-Bold', fontSize=11, textColor=BLACK,  spaceBefore=12, spaceAfter=6)
    body_style    = style('Body',   fontName='Helvetica',      fontSize=9,  textColor=SLATE)
    cell_style    = style('Cell',   fontName='Helvetica',      fontSize=8,  textColor=BLACK,  leading=12)
    cell_bold     = style('CellB',  fontName='Helvetica-Bold', fontSize=8,  textColor=BLACK,  leading=12)
    cell_right    = style('CellR',  fontName='Helvetica',      fontSize=8,  textColor=DANGER, leading=12, alignment=TA_RIGHT)
    head_style    = style('Head',   fontName='Helvetica-Bold', fontSize=8,  textColor=WHITE,  leading=12, alignment=TA_CENTER)
    small_style   = style('Small',  fontName='Helvetica',      fontSize=7,  textColor=SLATE,  alignment=TA_CENTER)

    # ── Build document in memory ─────────────────────────────────────────
    buffer = io.BytesIO()
    W, H = A4
    LEFT = RIGHT = TOP = BOTTOM = 18*mm

    # Page number footer callback
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(SLATE)
        page_text = f"ExpenseFlow  ·  Confidential  ·  Page {doc.page}"
        canvas.drawCentredString(W / 2, BOTTOM - 6*mm, page_text)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=LEFT, rightMargin=RIGHT,
        topMargin=TOP, bottomMargin=BOTTOM + 8*mm,
        title=f"ExpenseFlow Report – {month_label}",
        author=user.username,
    )

    story = []
    col_w = W - LEFT - RIGHT  # usable width

    # ── 1. Header Banner ─────────────────────────────────────────────────
    header_data = [[
        Paragraph(f"ExpenseFlow", title_style),
        Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", sub_style),
    ]]
    header_table = Table(header_data, colWidths=[col_w * 0.65, col_w * 0.35])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), INDIGO),
        ('TOPPADDING',  (0,0), (-1,-1), 14),
        ('BOTTOMPADDING',(0,0),(-1,-1), 14),
        ('LEFTPADDING', (0,0), (0,-1), 16),
        ('RIGHTPADDING',(-1,0),(-1,-1), 16),
        ('ALIGN',       (1,0), (1,0), 'RIGHT'),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6*mm))

    # ── 2. Report title + user info ──────────────────────────────────────
    story.append(Paragraph(f"Expense Report — {month_label}", section_style))
    info_data = [[
        Paragraph(f"<b>Account:</b> {user.username}", body_style),
        Paragraph(f"<b>Email:</b> {user.email}", body_style),
        Paragraph(f"<b>Period:</b> {month_label}", body_style),
    ]]
    info_table = Table(info_data, colWidths=[col_w/3]*3)
    info_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0),(-1,-1), INDIGO_LIGHT),
        ('TOPPADDING',  (0,0),(-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('LEFTPADDING', (0,0),(-1,-1), 10),
        ('BOX',         (0,0),(-1,-1), 0.5, BORDER),
        ('ROUNDEDCORNERS',[4,4,4,4]),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5*mm))

    # ── 3. Summary Stats ─────────────────────────────────────────────────
    story.append(Paragraph("Summary", section_style))

    def stat_cell(label, value, color=BLACK):
        return [
            Paragraph(label, small_style),
            Paragraph(value, ParagraphStyle('sv', fontName='Helvetica-Bold', fontSize=14,
                                            textColor=color, alignment=TA_CENTER)),
        ]

    rem_color = SUCCESS if remaining >= 0 else DANGER
    stats_data = [
        [Paragraph("TOTAL SPENT", small_style),
         Paragraph("MONTHLY BUDGET", small_style),
         Paragraph("REMAINING", small_style),
         Paragraph("TRANSACTIONS", small_style)],
        [Paragraph(f"₹{total_spent:,.2f}", ParagraphStyle('sv1', fontName='Helvetica-Bold', fontSize=14, textColor=INDIGO, alignment=TA_CENTER)),
         Paragraph(f"₹{budget:,.2f}",      ParagraphStyle('sv2', fontName='Helvetica-Bold', fontSize=14, textColor=BLACK, alignment=TA_CENTER)),
         Paragraph(f"₹{abs(remaining):,.2f}", ParagraphStyle('sv3', fontName='Helvetica-Bold', fontSize=14, textColor=rem_color, alignment=TA_CENTER)),
         Paragraph(str(len(month_expenses)), ParagraphStyle('sv4', fontName='Helvetica-Bold', fontSize=14, textColor=SLATE, alignment=TA_CENTER))],
    ]
    stats_table = Table(stats_data, colWidths=[col_w/4]*4)
    stats_table.setStyle(TableStyle([
        ('BOX',          (0,0),(-1,-1), 0.5, BORDER),
        ('INNERGRID',    (0,0),(-1,-1), 0.5, BORDER),
        ('BACKGROUND',   (0,0),(-1,0), INDIGO_LIGHT),
        ('TOPPADDING',   (0,0),(-1,-1), 10),
        ('BOTTOMPADDING',(0,0),(-1,-1), 10),
        ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 5*mm))

    # ── 4. Category Breakdown ─────────────────────────────────────────────
    if cat_sorted:
        story.append(Paragraph("Category Breakdown", section_style))
        cat_head = [
            Paragraph("Category",   head_style),
            Paragraph("Amount",     head_style),
            Paragraph("% of Total", head_style),
        ]
        cat_rows = [cat_head]
        for i, (cat, amt) in enumerate(cat_sorted):
            pct = (amt / total_spent * 100) if total_spent > 0 else 0
            bg = ROW_ALT if i % 2 == 0 else WHITE
            cat_rows.append([
                Paragraph(cat,                    cell_style),
                Paragraph(f"₹{amt:,.2f}",         cell_bold),
                Paragraph(f"{pct:.1f}%",           cell_style),
            ])

        cat_table = Table(cat_rows, colWidths=[col_w*0.5, col_w*0.25, col_w*0.25])
        cat_style_rules = TableStyle([
            ('BACKGROUND',   (0,0),(-1,0), INDIGO),
            ('TEXTCOLOR',    (0,0),(-1,0), WHITE),
            ('BOX',          (0,0),(-1,-1), 0.5, BORDER),
            ('INNERGRID',    (0,0),(-1,-1), 0.3, BORDER),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ('ALIGN',        (1,0),(-1,-1), 'RIGHT'),
            ('ALIGN',        (0,0),(0,-1), 'LEFT'),
        ])
        for i in range(1, len(cat_rows)):
            if i % 2 == 0:
                cat_style_rules.add('BACKGROUND', (0,i), (-1,i), ROW_ALT)
        cat_table.setStyle(cat_style_rules)
        story.append(cat_table)
        story.append(Spacer(1, 5*mm))

    # ── 5. Expense List ───────────────────────────────────────────────────
    target = month_expenses if month_expenses else all_expenses[:50]
    label_scope = month_label if month_expenses else "All Time (latest 50)"
    story.append(Paragraph(f"Expense List — {label_scope}", section_style))

    exp_head = [
        Paragraph("Date",           head_style),
        Paragraph("Category",       head_style),
        Paragraph("Description",    head_style),
        Paragraph("Method",         head_style),
        Paragraph("Amount",         head_style),
    ]
    exp_rows = [exp_head]
    for i, e in enumerate(target):
        desc = (e.description or '—')[:45]
        exp_rows.append([
            Paragraph(e.date,                   cell_style),
            Paragraph(e.category,               cell_style),
            Paragraph(desc,                     cell_style),
            Paragraph(e.payment_method or '—',  cell_style),
            Paragraph(f"₹{e.amount:,.2f}",      cell_right),
        ])

    # Total row
    exp_rows.append([
        Paragraph("", cell_style),
        Paragraph("", cell_style),
        Paragraph("", cell_style),
        Paragraph("TOTAL", cell_bold),
        Paragraph(f"₹{sum(e.amount for e in target):,.2f}",
                  ParagraphStyle('tot', fontName='Helvetica-Bold', fontSize=8,
                                 textColor=INDIGO, alignment=TA_RIGHT)),
    ])

    col_widths = [col_w*0.13, col_w*0.18, col_w*0.35, col_w*0.16, col_w*0.18]
    exp_table = Table(exp_rows, colWidths=col_widths, repeatRows=1)
    exp_style = TableStyle([
        ('BACKGROUND',    (0,0),(-1,0), INDIGO),
        ('TEXTCOLOR',     (0,0),(-1,0), WHITE),
        ('BOX',           (0,0),(-1,-1), 0.5, BORDER),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, BORDER),
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('ALIGN',         (4,0),(-1,-1), 'RIGHT'),
        # Total row highlight
        ('BACKGROUND',    (0,-1),(-1,-1), INDIGO_LIGHT),
        ('LINEABOVE',     (0,-1),(-1,-1), 1, INDIGO),
    ])
    for i in range(1, len(exp_rows) - 1):
        if i % 2 == 0:
            exp_style.add('BACKGROUND', (0,i), (-1,i), ROW_ALT)
    exp_table.setStyle(exp_style)
    story.append(exp_table)

    # ── Build PDF ────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)

    filename = f"ExpenseFlow_Report_{sel_dt.strftime('%B_%Y')}.pdf"
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
