"""
Report Generator for ACMP.

Generates audit-ready reports in PDF, CSV, and ZIP formats.
"""
import io
import zipfile
import csv
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class ReportGeneratorError(Exception):
    """Base exception for report generator errors."""
    pass


class ReportGenerator:
    """
    Generates compliance reports in multiple formats.
    
    Supported formats:
    - PDF (professional audit-ready format)
    - CSV (spreadsheet-compatible)
    - ZIP (complete evidence package)
    """
    
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = output_dir
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a2e'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#16213e'),
            spaceAfter=12
        ))
    
    async def generate_report(
        self,
        tenant_id: str,
        framework_id: str,
        framework_name: str,
        controls: list[dict[str, Any]],
        violations: list[dict[str, Any]],
        period_start: datetime,
        period_end: datetime,
        format: str = "pdf"
    ) -> dict[str, Any]:
        """
        Generate compliance report.
        
        Args:
            tenant_id: Tenant ID.
            framework_id: Framework ID.
            framework_name: Framework display name.
            controls: List of control results.
            violations: List of violations.
            period_start: Report period start.
            period_end: Report period end.
            format: Output format (pdf, csv, zip).
            
        Returns:
            Report metadata with download path.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_id = f"rpt_{tenant_id}_{framework_id}_{timestamp}"
        
        if format == "pdf":
            content = await self.generate_pdf(
                framework_name, controls, violations, period_start, period_end
            )
            filename = f"{report_id}.pdf"
        elif format == "csv":
            content = await self.generate_csv(controls)
            filename = f"{report_id}.csv"
        elif format == "zip":
            content = await self.generate_zip(
                framework_name, controls, violations, period_start, period_end
            )
            filename = f"{report_id}.zip"
        else:
            raise ReportGeneratorError(f"Unsupported format: {format}")
        
        return {
            "report_id": report_id,
            "status": "generated",
            "format": format,
            "filename": filename,
            "size_bytes": len(content),
            "generated_at": datetime.utcnow().isoformat(),
            "content": content  # In production, store to S3 and return URL
        }
    
    async def generate_pdf(
        self,
        framework_name: str,
        controls: list[dict[str, Any]],
        violations: list[dict[str, Any]],
        period_start: datetime,
        period_end: datetime
    ) -> bytes:
        """
        Generate PDF report.
        
        Args:
            framework_name: Framework display name.
            controls: List of control results.
            violations: List of violations.
            period_start: Report period start.
            period_end: Report period end.
            
        Returns:
            PDF bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch
        )
        
        elements = []
        
        # Title
        elements.append(Paragraph(f"{framework_name} Compliance Report", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Report metadata
        elements.append(Paragraph(f"Report Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", self.styles['Normal']))
        elements.append(Paragraph(f"Period: {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}", self.styles['Normal']))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Executive Summary
        elements.append(Paragraph("Executive Summary", self.styles['SectionHeading']))
        summary_data = self._calculate_summary(controls, violations)
        summary_text = f"""
        Total Controls: {summary_data['total_controls']}<br/>
        Passing: {summary_data['passing']} ({summary_data['pass_percent']:.1f}%)<br/>
        Failing: {summary_data['failing']}<br/>
        Partial: {summary_data['partial']}<br/>
        Open Violations: {summary_data['open_violations']}<br/>
        Critical Violations: {summary_data['critical_violations']}
        """
        elements.append(Paragraph(summary_text, self.styles['Normal']))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Control Matrix
        elements.append(Paragraph("Control Matrix", self.styles['SectionHeading']))
        control_table = self._create_control_table(controls)
        elements.append(control_table)
        elements.append(PageBreak())
        
        # Violations
        if violations:
            elements.append(Paragraph("Open Violations", self.styles['SectionHeading']))
            violation_table = self._create_violation_table(violations)
            elements.append(violation_table)
        
        # Build PDF
        doc.build(elements)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    async def generate_csv(self, controls: list[dict[str, Any]]) -> bytes:
        """
        Generate CSV report.
        
        Args:
            controls: List of control results.
            
        Returns:
            CSV bytes.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        # Header
        writer.writerow([
            'Control ID',
            'Control Name',
            'Status',
            'Evidence Count',
            'Confidence',
            'Last Evaluated',
            'Violations'
        ])
        
        # Data rows
        for control in controls:
            writer.writerow([
                control.get('id', ''),
                control.get('name', ''),
                control.get('status', ''),
                control.get('evidence_count', 0),
                control.get('confidence', ''),
                control.get('evaluated_at', ''),
                control.get('violation_count', 0)
            ])
        
        buffer.seek(0)
        return buffer.getvalue().encode('utf-8')
    
    async def generate_zip(
        self,
        framework_name: str,
        controls: list[dict[str, Any]],
        violations: list[dict[str, Any]],
        period_start: datetime,
        period_end: datetime
    ) -> bytes:
        """
        Generate ZIP package with complete evidence.
        
        Args:
            framework_name: Framework display name.
            controls: List of control results.
            violations: List of violations.
            period_start: Report period start.
            period_end: Report period end.
            
        Returns:
            ZIP bytes.
        """
        buffer = io.BytesIO()
        
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add PDF report
            pdf_content = await self.generate_pdf(
                framework_name, controls, violations, period_start, period_end
            )
            zip_file.writestr("compliance_report.pdf", pdf_content)
            
            # Add CSV export
            csv_content = await self.generate_csv(controls)
            zip_file.writestr("control_matrix.csv", csv_content)
            
            # Add summary JSON
            summary = self._calculate_summary(controls, violations)
            import json
            summary_json = json.dumps(summary, indent=2, default=str)
            zip_file.writestr("summary.json", summary_json)
            
            # Add manifest
            manifest = f"""Compliance Report Package
Generated: {datetime.utcnow().isoformat()}
Framework: {framework_name}
Period: {period_start.isoformat()} to {period_end.isoformat()}
Total Controls: {summary['total_controls']}
Pass Rate: {summary['pass_percent']:.1f}%
"""
            zip_file.writestr("MANIFEST.txt", manifest)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_control_table(self, controls: list[dict[str, Any]]) -> Table:
        """Create control matrix table."""
        data = [['Control ID', 'Name', 'Status', 'Evidence', 'Confidence']]
        
        for control in controls:
            status = control.get('status', 'UNKNOWN')
            status_color = {
                'PASS': colors.green,
                'FAIL': colors.red,
                'PARTIAL': colors.orange,
                'NOT_EVALUATED': colors.gray
            }.get(status, colors.gray)
            
            data.append([
                control.get('id', ''),
                control.get('name', '')[:50] + '...' if len(control.get('name', '')) > 50 else control.get('name', ''),
                Paragraph(f"<b>{status}</b>", self.styles['Normal']),
                str(control.get('evidence_count', 0)),
                control.get('confidence', '')
            ])
        
        table = Table(data, colWidths=[1.2*inch, 3*inch, 1*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        return table
    
    def _create_violation_table(self, violations: list[dict[str, Any]]) -> Table:
        """Create violations table."""
        data = [['ID', 'Control', 'Severity', 'Description', 'Age (days)']]
        
        for violation in violations:
            severity = violation.get('severity', 'MEDIUM')
            severity_color = {
                'LOW': colors.green,
                'MEDIUM': colors.orange,
                'HIGH': colors.red,
                'CRITICAL': colors.darkred
            }.get(severity, colors.black)
            
            data.append([
                violation.get('id', '')[:8],
                violation.get('control_id', ''),
                Paragraph(f"<b><font color='{severity_color.hexval()}'>{severity}</font></b>", self.styles['Normal']),
                violation.get('description', '')[:60] + '...' if len(violation.get('description', '')) > 60 else violation.get('description', ''),
                str(violation.get('age_days', 0))
            ])
        
        table = Table(data, colWidths=[1*inch, 1.2*inch, 1*inch, 4*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        return table
    
    def _calculate_summary(
        self,
        controls: list[dict[str, Any]],
        violations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Calculate summary statistics."""
        total = len(controls)
        passing = sum(1 for c in controls if c.get('status') == 'PASS')
        failing = sum(1 for c in controls if c.get('status') == 'FAIL')
        partial = sum(1 for c in controls if c.get('status') == 'PARTIAL')
        
        open_violations = sum(1 for v in violations if v.get('status') == 'OPEN')
        critical_violations = sum(1 for v in violations if v.get('severity') == 'CRITICAL' and v.get('status') == 'OPEN')
        
        return {
            'total_controls': total,
            'passing': passing,
            'failing': failing,
            'partial': partial,
            'pass_percent': (passing / total * 100) if total > 0 else 0,
            'open_violations': open_violations,
            'critical_violations': critical_violations,
            'generated_at': datetime.utcnow().isoformat()
        }
