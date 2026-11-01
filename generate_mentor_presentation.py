#!/usr/bin/env python3
"""
generate_mentor_presentation.py
Generates the comprehensive, structured PPT report for faculty mentor presentation
reflecting:
1. Team credentials & course details (Slide 1 preserved exactly)
2. Introduction & Problem Definition
3. Feedback & Actions taken from Review 1 (26/09/2026) and Review 2 (24/10/2026)
4. Technical Viva defense on Frontend HTML/CSS/JS selectors
5. 50% Progress Done (System Architecture, XGBoost ML, Physics, Dual Consoles)
6. How the system is used in practice
7. Future Planning & Remaining 50% Roadmap (Cloud scale, Live APIs, ST-GNN, MARL + SUMO)
8. Next steps & Sprint timeline
9. Guidance requested from Faculty Mentor (Dr. Rashmi Mothkur)
10. References & Literature Survey

Every slide incorporates the official Alliance University NAAC A+ accredited logo banner.
"""

import os
import shutil
import zipfile
import xml.etree.ElementTree as ET

SOURCE_EXTRACT_DIR = "/tmp/pptx_source"
BUILD_DIR = "/tmp/pptx_build"
OUTPUT_PPTX = "/Users/ak/Documents/Dp-01/AI_Smart_Traffic_System_Progress_and_Future_Report.pptx"

def create_slide_rels(has_arch_diagram=False):
    rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout2.xml"/>',
        '  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>'
    ]
    if has_arch_diagram:
        rels.append('  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image4.png"/>')
    rels.append('</Relationships>')
    return '\n'.join(rels)

def logo_pic_xml(pic_id=2):
    return f"""
    <p:pic>
      <p:nvPicPr>
        <p:cNvPr id="{pic_id}" name="Alliance University Logo"/>
        <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
        <p:nvPr/>
      </p:nvPicPr>
      <p:blipFill>
        <a:blip r:embed="rId2"/>
        <a:stretch><a:fillRect/></a:stretch>
      </p:blipFill>
      <p:spPr>
        <a:xfrm>
          <a:off x="8754256" y="134859"/>
          <a:ext cx="3184992" cy="563562"/>
        </a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
      </p:spPr>
    </p:pic>
    """

def xml_escape(text):
    if not isinstance(text, str):
        return text
    # Replace & first, but avoid double escaping
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def header_xml(title_text, subtitle_text="", title_id=10):
    title_text = xml_escape(title_text)
    subtitle_text = xml_escape(subtitle_text)
    sub_xml = ""
    if subtitle_text:
        sub_xml = f"""
        <p:sp>
          <p:nvSpPr>
            <p:cNvPr id="{title_id+1}" name="Subtitle"/>
            <p:cNvSpPr/>
            <p:nvPr/>
          </p:nvSpPr>
          <p:spPr>
            <a:xfrm>
              <a:off x="609600" y="850000"/>
              <a:ext cx="8000000" cy="350000"/>
            </a:xfrm>
          </p:spPr>
          <p:txBody>
            <a:bodyPr vert="horz" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0"/>
            <a:lstStyle/>
            <a:p>
              <a:pPr algn="l"/>
              <a:r>
                <a:rPr lang="en-US" sz="1300" i="1">
                  <a:solidFill><a:srgbClr val="475569"/></a:solidFill>
                  <a:latin typeface="Arial"/>
                </a:rPr>
                <a:t>{subtitle_text}</a:t>
              </a:r>
            </a:p>
          </p:txBody>
        </p:sp>
        """
    return f"""
    <p:sp>
      <p:nvSpPr>
        <p:cNvPr id="{title_id}" name="Slide Title"/>
        <p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
        <p:nvPr><p:ph type="title"/></p:nvPr>
      </p:nvSpPr>
      <p:spPr>
        <a:xfrm>
          <a:off x="609600" y="228599"/>
          <a:ext cx="8000000" cy="620000"/>
        </a:xfrm>
      </p:spPr>
      <p:txBody>
        <a:bodyPr vert="horz" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0"/>
        <a:lstStyle/>
        <a:p>
          <a:pPr algn="l"/>
          <a:r>
            <a:rPr lang="en-US" sz="2400" b="1">
              <a:solidFill><a:srgbClr val="1E3A8A"/></a:solidFill>
              <a:latin typeface="Arial"/>
            </a:rPr>
            <a:t>{title_text}</a:t>
          </a:r>
        </a:p>
      </p:txBody>
    </p:sp>
    {sub_xml}
    """

def text_card_xml(sp_id, x, y, cx, cy, title, bullets, bg_color="F8FAFC", border_color="CBD5E1"):
    bullets_xml = []
    if title:
        safe_title = xml_escape(title)
        bullets_xml.append(f"""
        <a:p>
          <a:pPr algn="l" spcAft="80000"/>
          <a:r>
            <a:rPr lang="en-US" sz="1400" b="1">
              <a:solidFill><a:srgbClr val="0F172A"/></a:solidFill>
              <a:latin typeface="Arial"/>
            </a:rPr>
            <a:t>{safe_title}</a:t>
          </a:r>
        </a:p>
        """)
    
    for bold_prefix, text in bullets:
        prefix_xml = ""
        if bold_prefix:
            safe_prefix = xml_escape(bold_prefix)
            prefix_xml = f"""
            <a:r>
              <a:rPr lang="en-US" sz="1150" b="1">
                <a:solidFill><a:srgbClr val="1E293B"/></a:solidFill>
                <a:latin typeface="Arial"/>
              </a:rPr>
              <a:t>{safe_prefix}: </a:t>
            </a:r>
            """
        safe_text = xml_escape(text)
        bullets_xml.append(f"""
        <a:p>
          <a:pPr marL="240000" indent="-240000" spcAft="50000">
            <a:buFont typeface="Arial"/>
            <a:buChar char="•"/>
          </a:pPr>
          {prefix_xml}
          <a:r>
            <a:rPr lang="en-US" sz="1150">
              <a:solidFill><a:srgbClr val="334155"/></a:solidFill>
              <a:latin typeface="Arial"/>
            </a:rPr>
            <a:t>{safe_text}</a:t>
          </a:r>
        </a:p>
        """)
        
    all_p = "\n".join(bullets_xml)
    return f"""
    <p:sp>
      <p:nvSpPr>
        <p:cNvPr id="{sp_id}" name="Card {sp_id}"/>
        <p:cNvSpPr/>
        <p:nvPr/>
      </p:nvSpPr>
      <p:spPr>
        <a:xfrm>
          <a:off x="{x}" y="{y}"/>
          <a:ext cx="{cx}" cy="{cy}"/>
        </a:xfrm>
        <a:prstGeom prst="roundRect">
          <a:avLst><a:gd name="adj" fmla="val 1200"/></a:avLst>
        </a:prstGeom>
        <a:solidFill><a:srgbClr val="{bg_color}"/></a:solidFill>
        <a:ln w="12700"><a:solidFill><a:srgbClr val="{border_color}"/></a:solidFill></a:ln>
      </p:spPr>
      <p:txBody>
        <a:bodyPr vert="horz" lIns="180000" tIns="140000" rIns="180000" bIns="140000" rtlCol="0" anchor="t"/>
        <a:lstStyle/>
        {all_p}
      </p:txBody>
    </p:sp>
    """

def table_xml(table_id, x, y, cx, cy, col_widths, headers, rows):
    grid_xml = "\n".join([f'<a:gridCol w="{w}"/>' for w in col_widths])
    header_cells = []
    for h in headers:
        safe_h = xml_escape(h)
        header_cells.append(f"""
        <a:tc>
          <a:txBody>
            <a:bodyPr anchor="ctr"/>
            <a:lstStyle/>
            <a:p>
              <a:pPr algn="l"/>
              <a:r>
                <a:rPr lang="en-US" sz="1100" b="1">
                  <a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>
                  <a:latin typeface="Arial"/>
                </a:rPr>
                <a:t>{safe_h}</a:t>
              </a:r>
            </a:p>
          </a:txBody>
          <a:tcPr marL="90000" marR="90000" marT="50000" marB="50000">
            <a:solidFill><a:srgbClr val="1E3A8A"/></a:solidFill>
          </a:tcPr>
        </a:tc>
        """)
    header_row_xml = f'<a:tr h="450000">{"".join(header_cells)}</a:tr>'
    
    body_rows_xml = []
    for r_idx, row in enumerate(rows):
        bg = "FFFFFF" if r_idx % 2 == 0 else "F1F5F9"
        cells = []
        for c in row:
            safe_c = xml_escape(c)
            cells.append(f"""
            <a:tc>
              <a:txBody>
                <a:bodyPr anchor="ctr"/>
                <a:lstStyle/>
                <a:p>
                  <a:pPr algn="l"/>
                  <a:r>
                    <a:rPr lang="en-US" sz="1000">
                      <a:solidFill><a:srgbClr val="1E293B"/></a:solidFill>
                      <a:latin typeface="Arial"/>
                    </a:rPr>
                    <a:t>{safe_c}</a:t>
                  </a:r>
                </a:p>
              </a:txBody>
              <a:tcPr marL="90000" marR="90000" marT="40000" marB="40000">
                <a:solidFill><a:srgbClr val="{bg}"/></a:solidFill>
              </a:tcPr>
            </a:tc>
            """)
        body_rows_xml.append(f'<a:tr h="400000">{"".join(cells)}</a:tr>')
        
    all_rows = header_row_xml + "\n" + "\n".join(body_rows_xml)
    
    return f"""
    <p:graphicFrame>
      <p:nvGraphicFramePr>
        <p:cNvPr id="{table_id}" name="Table {table_id}"/>
        <p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>
        <p:nvPr/>
      </p:nvGraphicFramePr>
      <p:xfrm>
        <a:off x="{x}" y="{y}"/>
        <a:ext cx="{cx}" cy="{cy}"/>
      </p:xfrm>
      <a:graphic>
        <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
          <a:tbl>
            <a:tblPr firstRow="1" bandRow="1">
              <a:tableStyleId>{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}</a:tableStyleId>
            </a:tblPr>
            <a:tblGrid>
              {grid_xml}
            </a:tblGrid>
            {all_rows}
          </a:tbl>
        </a:graphicData>
      </a:graphic>
    </p:graphicFrame>
    """

def wrap_slide_xml(shapes_xml):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" 
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" 
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
  <p:cSld>
    <p:bg>
      <p:bgPr>
        <a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>
        <a:effectLst/>
      </p:bgPr>
    </p:bg>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
      {shapes_xml}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""

print("Helper definitions loaded successfully.")

def build_all_slides():
    slides = {}
    
    # -------------------------------------------------------------------------
    # SLIDE 1: Title Slide (Preserved exactly as requested)
    # -------------------------------------------------------------------------
    # We read original slide1.xml directly to preserve exact format, but ensure clean XML
    with open(os.path.join(SOURCE_EXTRACT_DIR, "ppt/slides/slide1.xml"), "r", encoding="utf-8") as f:
        slides[1] = f.read()

    # -------------------------------------------------------------------------
    # SLIDE 2: Executive Agenda & Report Structure
    # -------------------------------------------------------------------------
    s2_shapes = [
        header_xml("Executive Agenda & Report Overview", "Comprehensive progress report and future roadmap for Faculty Mentor presentation"),
        logo_pic_xml(2),
        text_card_xml(20, 609600, 1350000, 5200000, 5100000, "1. Project Foundation & Progress", [
            ("Project Genesis & Problem Definition", "Urban congestion bottlenecks and necessity for predictive multi-horizon forecasting."),
            ("Review - I Feedback & Corrective Actions", "Overcoming stage fear, establishing work clarity, and dataset justification."),
            ("Review - II Feedback & System Advancements", "Rigorous XGBoost validation, multi-level risk analysis, and traffic rolling averages."),
            ("Frontend Technical Viva Clarification", "Comprehensive breakdown of HTML/CSS/JS architecture and selector categorization."),
            ("Current Progress (50% Operational Core)", "Verification of the 5 operational pillars running live on port 8089.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(21, 6200000, 1350000, 5382400, 5100000, "2. Operational Use & Future Planning", [
            ("ML Performance & Explainability", "XGBoost 74.22% accuracy, TreeSHAP local attribution, and Shannon entropy."),
            ("Parallel Dual Consoles", "Traveler navigation portal paired with municipal traffic control room."),
            ("Operational Utilization", "Real-world deployment workflows for commuters, traffic police, and urban planners."),
            ("Future Roadmap (Remaining 50%)", "Open traffic streaming APIs, Spatio-Temporal GNNs, MARL, and SUMO digital twin."),
            ("Next Steps & Mentor Requisition", "Milestone sprint schedule and targeted technical guidance from Dr. Rashmi Mothkur.")
        ], bg_color="F8FAFC", border_color="CBD5E1")
    ]
    slides[2] = wrap_slide_xml("\n".join(s2_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 3: Project Introduction & Problem Definition
    # -------------------------------------------------------------------------
    s3_shapes = [
        header_xml("Introduction & Problem Definition", "E1CSA313 Design Project - 1: AI-Based Smart Traffic Monitoring and Congestion Prediction"),
        logo_pic_xml(2),
        text_card_xml(30, 609600, 1350000, 5200000, 5100000, "The Urban Mobility Challenge", [
            ("Exponential Traffic Growth", "Rapid urbanization and vehicle density in Bangalore create severe recurring arterial bottlenecks."),
            ("Failure of Reactive Systems", "Conventional traffic monitors display only current delays; by the time congestion is visible, gridlock has occurred."),
            ("Economic & Environmental Toll", "Congestion causes massive fuel wastage, elevated carbon emissions, emergency vehicle delays, and lost productivity."),
            ("Need for Multi-Horizon Foresight", "Cities urgently require predictive models forecasting 15-, 30-, and 60-minute future traffic horizons.")
        ], bg_color="EFF6FF", border_color="BFDBFE"),
        text_card_xml(31, 6200000, 1350000, 5382400, 5100000, "Our Proposed Solution & Scope", [
            ("AI Predictive Engine", "XGBoost machine learning trained on 203k ground-truth corridor observations across 94 arterial roads."),
            ("Multi-Class Risk Horizon", "Predicts congestion severity across 4 distinct levels: Low, Moderate, High, and Severe."),
            ("Explainable Transparency", "Native TreeSHAP feature attributions identify the root causes (volume surge, rain, road capacity limit)."),
            ("Proactive Traffic Physics", "Integrates Greenshields hydrodynamic flow, Webster signal timing, and dynamic BPR Dijkstra bypass routing.")
        ], bg_color="F0FDF4", border_color="BBF7D0")
    ]
    slides[3] = wrap_slide_xml("\n".join(s3_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 4: Review - I Feedback & Corrective Actions
    # -------------------------------------------------------------------------
    s4_shapes = [
        header_xml("Review - I Evaluation Feedback & System Actions", "Evaluation Date: 26/09/2026 | Examiners: Dr. K. Madheswari & Prof. Swetha C.B."),
        logo_pic_xml(2),
        text_card_xml(40, 609600, 1350000, 5200000, 2450000, "Examiner Comments & Concerns", [
            ("Reviewer Remark 1", "Stage fear - Need to overcome, self practice rehearsal is required."),
            ("Reviewer Remark 2", "Require more clarity on the work and system formulation."),
            ("Reviewer Remark 3", "Which dataset is going to use? Lack of explicit dataset justification.")
        ], bg_color="FFF1F2", border_color="FECDD3"),
        text_card_xml(41, 6200000, 1350000, 5382400, 2450000, "Corrective Actions Taken", [
            ("Team Rehearsal Protocol", "Instituted structured presentation cards, individual speaking modules, and mock Q&A sessions."),
            ("Architectural Clarity", "Engineered formal 5-module system architecture specification with verified mathematical formulas."),
            ("Dataset Specification", "Validated Bangalore Urban Traffic Dataset (203,906 corridor rows, Jan 01 - Mar 26, 2026).")
        ], bg_color="F0FDF4", border_color="BBF7D0"),
        text_card_xml(42, 609600, 3950000, 10972800, 2500000, "Recommendation for Improvement: 'Have to do proper literature survey'", [
            ("10-Paper Comprehensive Survey", "Conducted rigorous literature review comparing Classical Time-Series, Deep Learning (Conv-LSTM, Soft-GRU, MSTT-MHA-WOA), and Decision Tree Ensembles."),
            ("Identified Literature Gaps", "Prior works suffered from synthetic data assumptions, lack of multi-horizon explainability, and absence of closed-loop signal actuation."),
            ("Strategic Design Outcome", "Selected XGBoost for optimal tabular efficiency, native TreeSHAP transparency, and deterministic millisecond inference latency.")
        ], bg_color="F8FAFC", border_color="E2E8F0")
    ]
    slides[4] = wrap_slide_xml("\n".join(s4_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 5: Review - II Feedback & System Advancements
    # -------------------------------------------------------------------------
    s5_shapes = [
        header_xml("Review - II Evaluation Feedback & Enhancements", "Evaluation Date: 24/10/2026 | Examiner: Dr. K. Madheswari (50% Scope Review)"),
        logo_pic_xml(2),
        text_card_xml(50, 609600, 1350000, 5200000, 5100000, "Reviewer Comments & Technical Audit", [
            ("Feedback 1: 'XGBoost - model'", "Examiner inspected the machine learning model architecture, feature engineering, and evaluation rigor."),
            ("Feedback 2: 'Risk Analysis'", "Examiner highlighted the need for actionable multi-level risk categorization beyond simple binary labels."),
            ("Feedback 3: 'Traffic data collection - average...'", "Examiner examined how traffic telemetry is aggregated, asking about average speeds and volumes across corridors."),
            ("Target 50% Milestone Approved", "Core machine learning and data pipeline confirmed operational; viva focused on frontend technical implementation.")
        ], bg_color="EFF6FF", border_color="BFDBFE"),
        text_card_xml(51, 6200000, 1350000, 5382400, 5100000, "System Implementation & Enhancements", [
            ("Rigorous Model Validation", "Evaluated 8-feature XGBoost on 11,520 held-out test records: 74.22% accuracy, 74.70% weighted F1, TreeSHAP attribution."),
            ("Multi-Level Risk Matrix", "Formulated 4-state Level of Service (Low, Moderate, High, Severe) with Shannon Entropy uncertainty scoring."),
            ("Corridor Telemetry Aggregates", "Implemented rolling averages for vehicular speed (km/h), volume (veh/hr), density (k=q/v), and capacity utilization ratio (V/C)."),
            ("Thread-Safe Serving Core", "Engineered Python 3.14 REST server on port 8089 with NIST PBKDF2 authentication and sub-5ms API latency.")
        ], bg_color="F0FDF4", border_color="BBF7D0")
    ]
    slides[5] = wrap_slide_xml("\n".join(s5_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 6: Review - II Technical Viva Defense: Frontend & Selectors
    # -------------------------------------------------------------------------
    s6_shapes = [
        header_xml("Review - II Technical Viva Defense: Frontend Selectors", "Direct resolution to examiner remark: 'Checked selectors, unable to differentiate between types selector'"),
        logo_pic_xml(2),
        table_xml(60, 609600, 1350000, 10972800, 4200000, 
                  [1800000, 2400000, 3200000, 3572800],
                  ["Selector Category", "CSS / DOM Syntax Example", "Implementation in Smart Traffic AI", "Technical Purpose & Scope"],
                  [
                      ["Tag / Element", "header, main, button, input", "styles.css: header, button { ... }", "Applies global typography, CSS reset, and default layout."],
                      ["Class Selector", ".app-header, .status-card, .btn-primary", "document.querySelectorAll('.zone-tile')", "Reusable component styling following modern modular CSS rules."],
                      ["ID Selector", "#roleConsoleBadge, #predictBtn", "document.getElementById('predictBtn')", "Unique element targeting for JS click events and state updates."],
                      ["Attribute Selector", "input[type='time'], [data-tab='user']", "document.querySelector('[data-role=\"admin\"]')", "Selects elements based on HTML attributes or accessibility states."],
                      ["Combinator / Child", ".card-body > .metric-row, .zone-grid .tile", "document.querySelectorAll('.zone-grid > div')", "Enforces strict parent-child scoping and avoids style leakage."],
                      ["Pseudo-Class / Elem", ":hover, :focus-visible, ::before", ".btn-primary:active { transform: scale(0.97); }", "Powers tactile haptic press feedback, active tabs, and highlights."]
                  ]),
        text_card_xml(61, 609600, 5650000, 10972800, 800000, "", [
            ("Viva Defense Summary", "Our frontend (index.html, styles.css, app.js) strictly decouples structure (semantic HTML5), presentation (modular CSS with class/pseudo selectors), and behavior (vanilla JS DOM event listeners bound to explicit ID selectors).")
        ], bg_color="F8FAFC", border_color="CBD5E1")
    ]
    slides[6] = wrap_slide_xml("\n".join(s6_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 7: Current Progress: Implemented 50% Operational Architecture
    # -------------------------------------------------------------------------
    s7_shapes = [
        header_xml("Current Progress: Implemented 50% Architecture", "Fully operational software core verified on port 8089 (Passing 7/7 automated test suites)"),
        logo_pic_xml(2),
        text_card_xml(70, 609600, 1350000, 3500000, 5100000, "1. Ingestion & Modeling", [
            ("Network Topology", "94 Bangalore corridors and 98 intersections modeled as a weighted directed graph across 6 zones."),
            ("Ground-Truth Dataset", "203,906 historical observations (Jan 01 - Mar 26, 2026) with zero synthetic mock data."),
            ("XGBoost Inference", "8 engineered features predicting 15/30/60 min congestion states."),
            ("TreeSHAP Explainability", "Native local attribution decomposing congestion root causes in plain English.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(71, 4300000, 1350000, 3600000, 5100000, "2. Physics & Actuation", [
            ("Greenshields Macroscopic", "Models speed-density-flow relationship: q = k * v with capacity limits."),
            ("Webster Signal Timing", "Calculates optimal minimum delay cycle time (C_0) and green phase splits (g_i)."),
            ("Dynamic BPR Dijkstra", "Bureau of Public Roads impedance inflation routing with alternate bypass."),
            ("Two-Phase Atomic Events", "POSIX atomic municipal event registry with dynamic injection and rerouting.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(72, 8100000, 1350000, 3482400, 5100000, "3. Serving & Consoles", [
            ("Production Server", "Python 3.14 ThreadingHTTPServer with REST JSON endpoints."),
            ("NIST Authentication", "PBKDF2-HMAC-SHA256 constant-time password hashing and role gating."),
            ("Road User Console", "Trip evaluation with departure time, bypass detours, and minutes saved."),
            ("Control Room Console", "6-zone heatmap, policy simulation sliders, and automated VMS broadcasts.")
        ], bg_color="F8FAFC", border_color="CBD5E1")
    ]
    slides[7] = wrap_slide_xml("\n".join(s7_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 8: System Architecture & Workflow Pipeline
    # -------------------------------------------------------------------------
    s8_shapes = [
        header_xml("End-to-End System Architecture & Data Flow", "Closed-loop pipeline: Telemetry Ingestion -> ML Inference -> Physics Actuation -> Parallel Serving"),
        logo_pic_xml(2),
        f"""
        <p:pic>
          <p:nvPicPr>
            <p:cNvPr id="80" name="System Architecture Diagram"/>
            <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
            <p:nvPr/>
          </p:nvPicPr>
          <p:blipFill>
            <a:blip r:embed="rId3"/>
            <a:stretch><a:fillRect/></a:stretch>
          </p:blipFill>
          <p:spPr>
            <a:xfrm>
              <a:off x="1000000" y="1300000"/>
              <a:ext cx="10192000" cy="5200000"/>
            </a:xfrm>
            <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
            <a:ln w="12700"><a:solidFill><a:srgbClr val="CBD5E1"/></a:solidFill></a:ln>
          </p:spPr>
        </p:pic>
        """
    ]
    slides[8] = wrap_slide_xml("\n".join(s8_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 9: Machine Learning Implementation & Model Metrics
    # -------------------------------------------------------------------------
    s9_shapes = [
        header_xml("Machine Learning Implementation & Empirical Metrics", "Verified evaluation on 11,520 held-out test observations (57,600 total dataset records)"),
        logo_pic_xml(2),
        table_xml(90, 609600, 1350000, 5200000, 2400000,
                  [2000000, 1600000, 1600000],
                  ["Evaluation Metric", "Empirical Value", "Benchmark Status"],
                  [
                      ["Overall Test Accuracy", "74.22%", "Production Standard"],
                      ["Weighted Precision", "75.38%", "High Target Reliability"],
                      ["Weighted Recall", "74.22%", "Balanced Sensitivity"],
                      ["Weighted F1-Score", "74.70%", "Robust Generalization"],
                      ["Test Set Size", "11,520 records", "Chronological Hold-out"]
                  ]),
        text_card_xml(91, 6000000, 1350000, 5582400, 2400000, "Model Architecture & Features", [
            ("Model Algorithm", "XGBoost (Extreme Gradient Boosting) Multi-Class Classifier."),
            ("8 Key Input Features", "Vehicular volume, speed, road capacity, occupancy ratio, hour of day, day of week, weather impact index, and rolling lag congestion."),
            ("Objective & Tuning", "Multi-class softprob with multi:softprob objective function, learning_rate=0.08, max_depth=6, subsample=0.85.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(92, 609600, 3950000, 10972800, 2500000, "Explainable AI (TreeSHAP) & Shannon Entropy Uncertainty", [
            ("Native TreeSHAP Attribution", "Decomposes each individual prediction into local additive feature contributions (pred_contribs=True). Plain-English outputs explain to users: 'Congestion driven 42% by volume surge, 28% by wet weather, and 18% by capacity bottleneck.'"),
            ("Shannon Uncertainty Entropy H(p)", "Calculates mathematical entropy over class probability distributions: H(p) = -sum(p_i * log2(p_i)). Flags border-case regime transitions where confidence drops, alerting operators to uncertain traffic dynamics.")
        ], bg_color="EFF6FF", border_color="BFDBFE")
    ]
    slides[9] = wrap_slide_xml("\n".join(s9_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 10: Operational Implementation: Dual-Console Interface
    # -------------------------------------------------------------------------
    s10_shapes = [
        header_xml("Operational Implementation: Dual-Console Interface", "Live interactive dashboard providing role-gated experiences for commuters and traffic managers"),
        logo_pic_xml(2),
        text_card_xml(100, 609600, 1350000, 5200000, 5100000, "Console A: Road User / Commuter Portal", [
            ("Direct Departure Scheduling", "Interactive calendar date picker (2026-01-01 to 2026-03-26) and 24-hour time selector (zero dummy presets)."),
            ("Predictive Horizon Badge", "Real-time Level of Service (Low / Moderate / High / Severe) with confidence score for 15, 30, and 60-minute windows."),
            ("Dynamic Bypass Detours", "BPR-weighted Dijkstra graph search recommends fastest alternate routes (e.g. bypass via RD_902 saves 9.3 minutes)."),
            ("Plain-English Cause Explanations", "TreeSHAP explanations translate model weights into clear motorist advice citing specific roadworks or volume spikes.")
        ], bg_color="F0FDF4", border_color="BBF7D0"),
        text_card_xml(101, 6200000, 1350000, 5382400, 5100000, "Console B: Traffic Management Control Room", [
            ("6-Zone Sector Heatmap", "Real-time geographical criticality monitoring across Tech Corridor, Central Core, Ring Roads, and Suburbs."),
            ("Counterfactual Policy Sliders", "Simulates traffic policy levers (e.g. 20% demand reduction or 10% speed boost) using Greenshields hydrodynamics."),
            ("Webster Signal Timing Actuator", "Calculates actuated cycle lengths (C_0) and green splits (g_i) to flush congested bottlenecks."),
            ("Dynamic Event Lifecycle", "POSIX two-phase atomic event injection (accidents, metro work) triggering immediate network rerouting.")
        ], bg_color="EFF6FF", border_color="BFDBFE")
    ]
    slides[10] = wrap_slide_xml("\n".join(s10_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 11: Practical Deployment & Operational Usage
    # -------------------------------------------------------------------------
    s11_shapes = [
        header_xml("How We Will Be Using This: Real-World Deployment", "Operational workflows translating predictive intelligence into city-wide congestion mitigation"),
        logo_pic_xml(2),
        text_card_xml(110, 609600, 1350000, 5200000, 2450000, "1. Municipal Traffic Police & Control Centers", [
            ("Proactive Bottleneck Relief", "Traffic operators receive severe congestion warnings 30-60 minutes ahead, deploying field wardens prior to gridlock."),
            ("Dynamic Signal Split Adjustments", "Webster-actuated phase times are piped to signal controllers to clear queued arterial junctions."),
            ("Automated MUTCD VMS Broadcasts", "Automatically publishes Variable Message Sign advisories across electronic overhead road gantries.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(111, 6200000, 1350000, 5382400, 2450000, "2. Urban Commuters & Fleet Logistics", [
            ("Informed Departure Times", "Citizens select optimal travel departure slots, shifting peak demand curve and reducing individual trip delays."),
            ("Verified Alternate Detours", "Dynamic routing diverts vehicles to secondary collector roads, saving an average of 8-15 minutes per trip."),
            ("Commercial Fleet Optimization", "Last-mile logistics operators route delivery trucks through low-risk corridors, lowering fuel costs.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(112, 609600, 3950000, 10972800, 2500000, "3. Urban Planning, Infrastructure Audits & Emergency Corridors", [
            ("Evidence-Based Road Expansion", "Historical congestion heatmaps highlight chronic structural bottlenecks requiring geometric flyovers or lane widening."),
            ("Counterfactual Policy Testing", "Municipal authorities simulate the impact of new bus priority lanes, congestion pricing, or roadworks before implementation."),
            ("Emergency Green Corridors", "Clears priority routes for ambulances and fire engines by dynamically holding conflicting approaches via Webster actuators.")
        ], bg_color="EFF6FF", border_color="BFDBFE")
    ]
    slides[11] = wrap_slide_xml("\n".join(s11_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 12: Future Roadmap: Remaining 50% Implementation Plan
    # -------------------------------------------------------------------------
    s12_shapes = [
        header_xml("Future Roadmap: Remaining 50% Cloud-Native Scale", "Phase 2 Expansion Architecture: Scaling from municipal prototype to enterprise cloud infrastructure"),
        logo_pic_xml(2),
        table_xml(120, 609600, 1350000, 10972800, 4800000,
                  [1800000, 2200000, 3600000, 3372800],
                  ["Phase 2 Pillar", "Weight", "Key Technical Components", "Core Deliverable & Expected Benefit"],
                  [
                      ["1. Streaming Telemetry", "10% Scope", "TomTom/HERE Open Traffic API Bridge, MQTT Edge, Rate-budgeting", "Real-time streaming city speeds without physical sensor road excavation."],
                      ["2. Frontier Spatial AI", "10% Scope", "Spatio-Temporal Graph Neural Networks (ST-GNN) & DCRNN", "Models spatial correlations across adjacent junctions and upstream waves."],
                      ["3. Multi-Agent RL", "10% Scope", "Multi-Agent PPO (MAPPO) & Eclipse SUMO Microscopic Twin", "Decentralized coordinated signal control across multi-intersection corridors."],
                      ["4. MLOps & Store", "10% Scope", "Feast Feature Store, Redis L1 cache, MLflow, Evidently drift audit", "Sub-10ms feature retrieval, continuous retraining, and data drift detection."],
                      ["5. Cloud & Mobile", "10% Scope", "Docker containerization, Kubernetes (EKS/GKE), React Native Mobile App", "Scales to 100,000+ concurrent commuters and municipal operations wall."]
                  ])
    ]
    slides[12] = wrap_slide_xml("\n".join(s12_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 13: Phase 2 Technical Deep-Dive: Streaming APIs & ST-GNN
    # -------------------------------------------------------------------------
    s13_shapes = [
        header_xml("Phase 2 Core Technical Deep-Dive", "Bridging live streaming data and frontier spatio-temporal deep learning"),
        logo_pic_xml(2),
        text_card_xml(130, 609600, 1350000, 5200000, 5100000, "Pillar 1: Open Traffic Flow API Ingestion", [
            ("Zero Hardware Procurement", "Connects to TomTom Traffic Flow API v4 and HERE Incident API via authenticated REST polling workers."),
            ("GPS-to-Corridor Spatial Mapper", "Binds geographic bounding boxes directly to our 94 Bangalore road graph segments."),
            ("Sliding Rate-Budget Manager", "Optimizes free-tier quota (2,500 daily calls) with 5-minute sliding query schedules prioritized for high-risk arterial roads."),
            ("Greenshields Feature Synthesizer", "Ingests live speeds, inverts traffic density (k = q / v), and computes real-time V/C ratios for continuous XGBoost inference.")
        ], bg_color="F0FDF4", border_color="BBF7D0"),
        text_card_xml(131, 6200000, 1350000, 5382400, 5100000, "Pillar 2: Spatio-Temporal Graph Neural Networks", [
            ("Beyond Independent Corridors", "Current tabular models treat corridors individually; ST-GNNs model the road network as a graph adjacency matrix A."),
            ("Diffusion Convolution (DCRNN)", "Captures directional upstream traffic shockwaves moving through downstream bottlenecks over time."),
            ("Multi-Intersection Digital Twin", "Couples PyTorch Geometric Graph Convolution with Eclipse SUMO microscopic simulator for multi-junction stress testing."),
            ("Hybrid Ensemble Benchmark", "Benchmarks ST-GNN accuracy and inference latency against our baseline XGBoost model.")
        ], bg_color="EFF6FF", border_color="BFDBFE")
    ]
    slides[13] = wrap_slide_xml("\n".join(s13_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 14: Next Steps & Immediate Sprint Execution Plan
    # -------------------------------------------------------------------------
    s14_shapes = [
        header_xml("Next Steps & Sprint Execution Plan", "Systematic four-sprint delivery roadmap leading to the Final Review and Project Defense"),
        logo_pic_xml(2),
        text_card_xml(140, 609600, 1350000, 2600000, 5100000, "Sprint 1 (Weeks 1-2)\nLive Telemetry Bridge", [
            ("TomTom Poller Integration", "Deploy live_api_poller.py worker for 94 corridors."),
            ("Rate Budget Optimization", "Configure caching and sliding polling intervals."),
            ("Telemetry Cache Layer", "Stream real-time speeds into active network topology graph.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(141, 3350000, 1350000, 2600000, 5100000, "Sprint 2 (Weeks 3-4)\nDigital Twin Simulation", [
            ("SUMO Network Setup", "Export Bangalore graph into SUMO road network."),
            ("Actuated Signal Tests", "Simulate multi-junction Webster coordinated splits."),
            ("Queue Dissipation Audit", "Measure bottleneck delay reductions under peak load.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(142, 6100000, 1350000, 2600000, 5100000, "Sprint 3 (Weeks 5-6)\nST-GNN Benchmarking", [
            ("PyTorch Geometric Model", "Train DCRNN graph model on corridor adjacency matrix."),
            ("Comparative Evaluation", "Benchmark ST-GNN accuracy and latency vs XGBoost."),
            ("Ensemble Serving", "Integrate best model into production REST API endpoint.")
        ], bg_color="F8FAFC", border_color="CBD5E1"),
        text_card_xml(143, 8850000, 1350000, 2732400, 5100000, "Sprint 4 (Weeks 7-8)\nFinal Polish & Viva", [
            ("Cloud Containerization", "Package full system with Docker and automated tests."),
            ("Technical Documentation", "Finalize IEEE project report and code documentation."),
            ("Rehearsal & Mock Viva", "Conduct team practice sessions to ensure confident defense.")
        ], bg_color="EFF6FF", border_color="BFDBFE")
    ]
    slides[14] = wrap_slide_xml("\n".join(s14_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 15: Conclusion & Faculty Mentor Guidance Requisition
    # -------------------------------------------------------------------------
    s15_shapes = [
        header_xml("Conclusion & Mentor Guidance Requisition", "Summary of accomplishments and specific guidance requested from Mentor Dr. Rashmi Mothkur"),
        logo_pic_xml(2),
        text_card_xml(150, 609600, 1350000, 5200000, 5100000, "Project Accomplishments Summary", [
            ("50% Functional Scope Delivered", "Engineered and verified a complete, working smart traffic monitoring and prediction prototype on port 8089."),
            ("Mathematical & Modeling Rigor", "Integrated Greenshields hydrodynamics, Webster signal timing, dynamic BPR Dijkstra, and 8-feature XGBoost with TreeSHAP explainability."),
            ("Reviewer Feedback Fully Resolved", "Addressed all Review 1 comments (rehearsal, clarity, dataset) and Review 2 comments (XGBoost validation, risk analysis, frontend selectors)."),
            ("Robust Software Quality", "Enforces thread-safe serving, NIST PBKDF2 security, and 100% automated test coverage across 7 test suites.")
        ], bg_color="F0FDF4", border_color="BBF7D0"),
        text_card_xml(151, 6200000, 1350000, 5382400, 5100000, "Technical Guidance Requested from Mentor", [
            ("Live Ingestion Feasibility", "Guidance on deploying the TomTom Open API bridge vs municipal open-data endpoints for Phase 2 validation."),
            ("Spatio-Temporal Model Selection", "Recommendations on ST-GNN vs DCRNN graph architectures suitable for academic publishing in Design Project - 1."),
            ("Multi-Intersection Actuation", "Faculty review of our Webster minimum delay coordination logic across adjacent corridor intersections."),
            ("Viva Preparation Guidance", "Feedback on team presentation delivery and technical defense strategy for the upcoming final evaluation.")
        ], bg_color="EFF6FF", border_color="BFDBFE")
    ]
    slides[15] = wrap_slide_xml("\n".join(s15_shapes))

    # -------------------------------------------------------------------------
    # SLIDE 16: References & Literature Foundation
    # -------------------------------------------------------------------------
    s16_shapes = [
        header_xml("References & Literature Survey Foundation", "Key peer-reviewed research papers guiding our system design and methodology"),
        logo_pic_xml(2),
        text_card_xml(160, 609600, 1350000, 10972800, 5100000, "", [
            ("1. Ithrees, R., et al. (2026)", "AI-Based Intelligent Traffic Management System. Explores AI integration for arterial corridor monitoring."),
            ("2. Vishnupriya, K., et al. (2026)", "AI-Enabled Smart Traffic Management for Real-Time Congestion Risk Prediction. IEEE ICICCS. Precision 0.91, 12ms latency."),
            ("3. Suhas, M. N., et al. (2026)", "AI Based Traffic Congestion Monitoring and Alert System. IEEE ICDCA. Multi-agent alert generation with 89.6% accuracy."),
            ("4. Rajendran, S., & Ayyasamy, B. (2020)", "Short-term traffic prediction model for urban transportation using structure pattern and regression: an Indian context. SN Applied Sciences."),
            ("5. Kumar, M., & Kumar, K. (2023)", "Traffic Congestion Prediction Using Categorized Vehicular Speed Data. Transportation Research Group (TRG)."),
            ("6. Jha, A., et al. (2026)", "Prediction of traffic congestion through Decision Tree, Queueing Theory, Deep Belief Network and Random Forest. Discover Applied Sciences."),
            ("7. Revathi, S., et al. (2026)", "Enhanced short-term traffic flow forecasting using a meteorological spatio-temporal transformer with multi-head attention. Scientific Reports."),
            ("8. Webster, F. V. (1958)", "Traffic Signal Settings. Road Research Technical Paper No. 39, HMSO, London. Foundation for optimal signal cycle length C_0."),
            ("9. Greenshields, B. D. (1935)", "A Study of Traffic Capacity. Highway Research Board Proceedings, Vol. 14. Fundamental macroscopic flow equation q = k * v.")
        ], bg_color="F8FAFC", border_color="CBD5E1")
    ]
    slides[16] = wrap_slide_xml("\n".join(s16_shapes))

    return slides

def repack_presentation(slides):
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    shutil.copytree(SOURCE_EXTRACT_DIR, BUILD_DIR)
    
    # 1. Clean existing slides directory
    slides_dir = os.path.join(BUILD_DIR, "ppt/slides")
    slides_rels_dir = os.path.join(slides_dir, "_rels")
    os.makedirs(slides_rels_dir, exist_ok=True)
    
    for f in os.listdir(slides_dir):
        if f.startswith("slide") and f.endswith(".xml"):
            os.remove(os.path.join(slides_dir, f))
    for f in os.listdir(slides_rels_dir):
        if f.startswith("slide") and f.endswith(".xml.rels"):
            os.remove(os.path.join(slides_rels_dir, f))
            
    # 2. Write new slide XMLs and rels
    total_slides = len(slides)
    for i in range(1, total_slides + 1):
        slide_path = os.path.join(slides_dir, f"slide{i}.xml")
        rels_path = os.path.join(slides_rels_dir, f"slide{i}.xml.rels")
        
        with open(slide_path, "w", encoding="utf-8") as f:
            f.write(slides[i])
            
        has_arch = (i == 8)
        with open(rels_path, "w", encoding="utf-8") as f:
            f.write(create_slide_rels(has_arch_diagram=has_arch))
            
    # 3. Update presentation.xml
    pres_path = os.path.join(BUILD_DIR, "ppt/presentation.xml")
    with open(pres_path, "r", encoding="utf-8") as f:
        pres_content = f.read()
        
    sld_id_items = []
    base_id = 1000
    for i in range(1, total_slides + 1):
        sld_id_items.append(f'<p:sldId id="{base_id + i}" r:id="rId{i+1}"/>')
    sld_id_str = "".join(sld_id_items)
    
    # Replace <p:sldIdLst>...</p:sldIdLst>
    start_tag = "<p:sldIdLst>"
    end_tag = "</p:sldIdLst>"
    idx1 = pres_content.find(start_tag)
    idx2 = pres_content.find(end_tag)
    new_pres_content = pres_content[:idx1 + len(start_tag)] + sld_id_str + pres_content[idx2:]
    
    with open(pres_path, "w", encoding="utf-8") as f:
        f.write(new_pres_content)
        
    # 4. Update ppt/_rels/presentation.xml.rels
    pres_rels_path = os.path.join(BUILD_DIR, "ppt/_rels/presentation.xml.rels")
    rels_lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    for i in range(1, total_slides + 1):
        rels_lines.append(f'  <Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
        
    # Add other needed relationships
    rels_lines.append(f'  <Relationship Id="rId{total_slides+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster" Target="notesMasters/notesMaster1.xml"/>')
    rels_lines.append(f'  <Relationship Id="rId{total_slides+3}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/handoutMaster" Target="handoutMasters/handoutMaster1.xml"/>')
    rels_lines.append(f'  <Relationship Id="rId{total_slides+4}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>')
    rels_lines.append(f'  <Relationship Id="rId{total_slides+5}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>')
    rels_lines.append('</Relationships>')
    
    with open(pres_rels_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rels_lines))
        
    # 5. Update [Content_Types].xml cleanly with ElementTree
    ct_path = os.path.join(BUILD_DIR, "[Content_Types].xml")
    ET.register_namespace("", "http://schemas.openxmlformats.org/package/2006/content-types")
    tree = ET.parse(ct_path)
    root = tree.getroot()
    
    # Remove existing slide overrides
    to_remove = []
    for elem in root:
        if elem.attrib.get("PartName", "").startswith("/ppt/slides/slide"):
            to_remove.append(elem)
    for elem in to_remove:
        root.remove(elem)
        
    # Add new slide overrides
    ns_ct = "http://schemas.openxmlformats.org/package/2006/content-types"
    for i in range(1, total_slides + 1):
        elem = ET.SubElement(root, f"{{{ns_ct}}}Override")
        elem.set("PartName", f"/ppt/slides/slide{i}.xml")
        elem.set("ContentType", "application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
        
    tree.write(ct_path, encoding="utf-8", xml_declaration=True)
        
    # 6. Zip into final .pptx file
    if os.path.exists(OUTPUT_PPTX):
        os.remove(OUTPUT_PPTX)
        
    with zipfile.ZipFile(OUTPUT_PPTX, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(BUILD_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, BUILD_DIR)
                z.write(full_path, rel_path)
                
    print(f"Successfully generated PPTX with {total_slides} slides: {OUTPUT_PPTX}")
    print(f"Output File Size: {os.path.getsize(OUTPUT_PPTX)} bytes")

if __name__ == "__main__":
    slides = build_all_slides()
    repack_presentation(slides)
