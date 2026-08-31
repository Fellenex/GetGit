#!/usr/bin/env python3
"""Generate ``docs/architecture.drawio`` from a declarative box/edge spec.

The architecture diagram is *generated*, not hand-drawn, so that refreshing
it at a release tag is a matter of editing the ``COLUMNS`` and ``EDGES``
tables below and re-running this script — no fiddling with drawio geometry by
hand, and the layout constraints stay satisfied by construction.

Run it from anywhere::

    python docs/generate_architecture.py

Layout rules encoded here (see ``.claude/guidelines.md`` for the "why"):

* Boxes live in fixed left-to-right columns: Client -> Endpoint/Application
  -> Service -> Repository/Writer -> Source/Models. Two satellite columns
  hold single-user classes beside the box that uses them.
* Every cross-column edge exits the RIGHT side of its source box and enters
  the LEFT side of its target (mirrored for right-to-left edges). Box heights
  are grown so all the arrows on a vertical side fan out with room.
* Same-column edges run top<->bottom, jogging out into a side lane when
  another box sits between the two endpoints.

To add a class: add it to the right column in ``COLUMNS`` and add its edges
to ``EDGES``. Heights, y-positions, anchor sides and fan-out fractions are
all computed. The handful of long cross-column diagonals that would clip a
box are routed explicitly in ``WP``/``FORCE`` (pass 3); if you move columns
around, re-check those.

After editing, verify the result: no two boxes overlap, and no edge segment
passes through a non-endpoint box.
"""
import html
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent / "architecture.drawio"

KIND = {
    "client": ("#dae8fc", "#6c8ebf", False), "green": ("#d5e8d4", "#82b366", False),
    "model":  ("#fff2cc", "#d6b656", False), "red":   ("#f8cecc", "#b85450", False),
    "purple": ("#e1d5e7", "#9673a6", False), "orange":("#ffe6cc", "#d79b00", False),
    "odash":  ("#ffe6cc", "#d79b00", True),
}
# column x -> (width, [ (id,label,kind), ... ] top-to-bottom)
COLUMNS = {
    60:  (200, [("main_module","__main__.py","client"),
                ("cli_main","cli/entrypoint.py\nmain()","client"),
                ("argument_parser","ArgumentParser","client")]),
    480: (240, [("application_run","application/main.py\nrun()","green"),
                ("app_settings","AppSettings","model"),
                ("user_state","UserState","model"),
                ("exit_code","ExitCode","model")]),
    900: (220, [("github_service","GithubService","red"),
                ("report_service","ReportService","red"),
                ("user_state_service","UserStateService","green")]),
    1320:(220, [("repo_provider","RepoProvider","purple"),
                ("pr_provider","PullRequestProvider","purple"),
                ("commit_provider","CommitProvider","purple"),
                ("csv_writer","CsvWriter","purple"),
                ("json_handler","JSONFileHandler","purple"),
                ("user_state_repo","UserStateRepository","green")]),
    1620:(200, [("repository_access_err","RepositoryAccessError","orange")]),
    1920:(220, [("github_client","GithubClient","orange"),
                ("github_settings","GithubSettings","model"),
                ("writer","Writer (Protocol)","odash"),
                ("pr_fetch_result","PullRequestFetchResult","model"),
                ("iso_date_parser","IsoDateParser","orange"),
                ("authorship_report","AuthorshipReport","model"),
                ("commit","Commit","model"),
                ("pull_request","PullRequest","model"),
                ("review","Review","model"),
                ("json_model","JSONModel","odash")]),
    2220:(200, [("rate_limit_err","RateLimitExceededError","orange")]),
}
# id -> {x, w, label, kind, order}
BOX = {}
COL_OF = {}
for cx,(w,items) in COLUMNS.items():
    for i,(bid,label,kind) in enumerate(items):
        BOX[bid] = {"x":cx,"w":w,"label":label,"kind":kind,"order":i}
        COL_OF[bid] = cx

# edges: (id, src, tgt, dashed)  -- dashed = inherits / implements / raises
EDGES = [
    ("e1","main_module","cli_main",False),
    ("e2","cli_main","argument_parser",False),
    ("e3","cli_main","application_run",False),
    ("e4","argument_parser","app_settings",False),
    ("e5","application_run","app_settings",False),
    ("e6","application_run","github_service",False),
    ("e7","application_run","report_service",False),
    ("e8","application_run","github_client",False),
    ("e9","application_run","github_settings",False),
    ("e14a","application_run","user_state_service",False),
    ("e14b","application_run","user_state",False),
    ("e_run_exit","application_run","exit_code",False),
    ("e14c","application_run","json_handler",False),
    ("e_run_usr","application_run","user_state_repo",False),
    ("e_uss_us","user_state_service","user_state",False),
    ("e_uss_repo","user_state_service","user_state_repo",False),
    ("e_usr1","user_state_repo","json_handler",False),
    ("e_usr2","user_state_repo","user_state",False),
    ("e_usr3","user_state_repo","iso_date_parser",False),
    ("e15","github_service","app_settings",False),
    ("e16","github_service","repo_provider",False),
    ("e17","github_service","pr_provider",False),
    ("e18","github_service","commit_provider",False),
    ("e19","report_service","csv_writer",False),
    ("e20","report_service","json_handler",False),
    ("e21","report_service","authorship_report",False),
    ("e22","repo_provider","github_client",False),
    ("e23","pr_provider","github_client",False),
    ("e24","commit_provider","github_client",False),
    ("e_pr_rae","pr_provider","repository_access_err",True),
    ("e25","pr_provider","pull_request",False),
    ("e26","pr_provider","review",False),
    ("e27","pr_provider","pr_fetch_result",False),
    ("e28","pr_provider","iso_date_parser",False),
    ("e29","commit_provider","commit",False),
    ("e30","csv_writer","writer",True),
    ("e31","csv_writer","json_model",False),
    ("e33","json_handler","json_model",False),
    ("e34","writer","json_model",True),
    ("e35","github_client","github_settings",False),
    ("e_gh_err","github_client","rate_limit_err",True),
    ("e36","pr_fetch_result","pull_request",False),
    ("e37","pr_fetch_result","review",False),
    ("e38","authorship_report","commit",False),
    ("e39","authorship_report","pull_request",False),
    ("e40","authorship_report","review",False),
    ("e41","authorship_report","json_model",True),
    ("e42","commit","json_model",True),
    ("e43","pull_request","json_model",True),
    ("e44","review","json_model",True),
    ("e_us_jm","user_state","json_model",True),
]

# ---- pass 1: assign sides (L/R/T/B) for each endpoint ----
def side_for(src,tgt):
    cs,ct = COL_OF[src], COL_OF[tgt]
    if cs < ct: return ("R","L")          # left -> right
    if cs > ct: return ("L","R")          # right -> left
    # same column: compare order
    if BOX[src]["order"] < BOX[tgt]["order"]: return ("B","T")
    return ("T","B")

def has_intermediate(s,t):
    """True if a box in the same column sits between s and t by order."""
    if COL_OF[s]!=COL_OF[t]: return False
    lo,hi=sorted((BOX[s]["order"],BOX[t]["order"]))
    return hi-lo>1

SIDES = {}
JOG = {}   # eid -> lane side ('L' or 'R') for same-column edges that skip a box
for eid,s,t,d in EDGES:
    ss,ts = side_for(s,t)
    if has_intermediate(s,t):
        lane = "R" if COL_OF[s]==1920 else "L"   # Source column jogs right (left side is busy)
        ss=ts=lane
        JOG[eid]=lane
    SIDES[eid]=(ss,ts)

# ---- pass 1b: box heights from max arrows on a vertical (L/R) side ----
cnt = defaultdict(int)
for eid,s,t,d in EDGES:
    ss,ts = SIDES[eid]
    if ss in "LR": cnt[(s,ss)] += 1
    if ts in "LR": cnt[(t,ts)] += 1
for bid,b in BOX.items():
    l = cnt[(bid,"L")]; r = cnt[(bid,"R")]
    b["h"] = max(60, max(l,r)*34)

# ---- pass 1c: stack y within each column ----
GAP = 70
for cx,(w,items) in COLUMNS.items():
    y = 60
    for bid,_,_ in items:
        BOX[bid]["y"] = y
        y += BOX[bid]["h"] + GAP
# nudge the two satellites to sit beside their single user, clear of the
# pr_provider/commit_provider -> github_client sightlines
BOX["repository_access_err"]["y"] = 130
BOX["rate_limit_err"]["y"] = 110

def cx_(b): return b["x"]+b["w"]/2
def cy_(b): return b["y"]+b["h"]/2

# ---- pass 2: distribute fractions per (box, side) ----
groups = defaultdict(list)   # (box,side) -> list of (eid, is_src)
for eid,s,t,d in EDGES:
    ss,ts = SIDES[eid]
    groups[(s,ss)].append((eid,True))
    groups[(t,ts)].append((eid,False))

FRAC = {}   # (eid, is_src) -> (fx,fy)
def other(eid,is_src):
    _,s,t,_ = next(e for e in EDGES if e[0]==eid)
    return BOX[t] if is_src else BOX[s]
for (bid,side),members in groups.items():
    if side in "LR":
        members.sort(key=lambda m: cy_(other(*m)))
        n=len(members)
        for i,(eid,is_src) in enumerate(members):
            fy = 0.5 if n==1 else 0.18 + (0.64*i/(n-1))
            fx = 1.0 if side=="R" else 0.0
            FRAC[(eid,is_src)] = (fx,round(fy,3))
    else:
        members.sort(key=lambda m: cx_(other(*m)))
        n=len(members)
        for i,(eid,is_src) in enumerate(members):
            fx = 0.5 if n==1 else 0.2 + (0.6*i/(n-1))
            fy = 1.0 if side=="B" else 0.0
            FRAC[(eid,is_src)] = (round(fx,3),fy)

# ---- pass 3: waypoints ----
WP = {}
FORCE = {}

# (a) auto lanes for same-column jog edges (skip a box in their column)
lane_k = defaultdict(int)
for eid,s,t,d in EDGES:
    if eid not in JOG: continue
    side = JOG[eid]
    cx = BOX[s]["x"]; w = BOX[s]["w"]
    k = lane_k[(cx,side)]; lane_k[(cx,side)] += 1
    lane = cx + w + 20 + k*12 if side=="R" else cx - 40 - k*14
    WP[eid] = [(lane, cy_(BOX[s])), (lane, cy_(BOX[t]))]

# (b) manual routing for the long cross-column diagonals that would clip boxes
WP.update({
    # run's far arrows ride the top margin, then drop in the col3.5/col4 gaps
    "e8":  [(745,50),(1900,50),(1900,120)],
    "e9":  [(760,44),(1885,44),(1885,300)],
    # run -> deep Repository boxes: drop below the Service column, low lane
    "e14c":[(800,715),(1255,715)],
    "e_run_usr":[(815,880),(1265,880)],
    # user_state -> json_model: low horizontal lane into json_model's left
    "e_us_jm":[(770,1150),(1885,1150)],
    # csv_writer -> json_model: drop past user_state_repo, low lane
    "e31":[(1585,1120),(1875,1120)],
    # report_service -> authorship_report: thread the Repository column's gap
    "e21":[(1250,690),(1760,690)],
})
FORCE.update({
    # keep pr_provider -> github_client below the RepositoryAccessError satellite
    "e23": ((1,0.35),(0,0.9)),
    "e8":  ((1,0.12),(0,None)),
    "e9":  ((1,0.2),(0,None)),
    "e14c":((1,None),(0,None)),
    "e_run_usr":((1,None),(0,None)),
    "e_us_jm":((1,None),(0,None)),
    "e31":((1,None),(0,None)),
    "e21":((1,None),(0,None)),
})

def anchors(eid):
    ex,ey = FRAC[(eid,True)]; nx,ny = FRAC[(eid,False)]
    if eid in FORCE:
        (fex,fey),(fnx,fny) = FORCE[eid]
        if fex is not None: ex=fex
        if fey is not None: ey=fey
        if fnx is not None: nx=fnx
        if fny is not None: ny=fny
    return ex,ey,nx,ny

# ---- emit ----
def box_xml(bid,b):
    fill,stroke,dash = KIND[b["kind"]]
    d=";dashed=1" if dash else ""
    val=html.escape(b["label"]).replace("\n","&#10;")
    st=f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke}{d};"
    return (f'<mxCell id="{bid}" value="{val}" style="{st}" parent="1" vertex="1">'
            f'<mxGeometry x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}" as="geometry"/></mxCell>')

def edge_xml(eid,s,t,dashed):
    ex,ey,nx,ny = anchors(eid)
    # Straight segments through the waypoints (NOT curved=1): drawio splines a
    # curved edge *through* its waypoints, which bows and loops badly once an
    # edge has more than a couple of them. Straight polylines follow the lanes
    # exactly as laid out here (and as the box-crossing self-check assumes).
    if dashed:
        st=(f"endArrow=block;endFill=0;dashed=1;html=1;rounded=0;"
            f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={nx};entryY={ny};exitPerimeter=1;entryDx=0;entryDy=0;")
    else:
        st=(f"endArrow=classic;html=1;rounded=0;"
            f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={nx};entryY={ny};exitPerimeter=1;entryDx=0;entryDy=0;")
    inner=""
    if eid in WP:
        pts="".join(f'<mxPoint x="{px}" y="{py}"/>' for px,py in WP[eid])
        inner=f'<Array as="points">{pts}</Array>'
    return (f'<mxCell id="{eid}" style="{st}" parent="1" source="{s}" target="{t}" edge="1">'
            f'<mxGeometry relative="1" as="geometry">{inner}</mxGeometry></mxCell>')

LEGEND=[("legend_title","Legend",14,1,0),
        ("legend_solid","solid arrow = uses / depends on",0,0,0),
        ("legend_dashed","dashed arrow = inherits / implements / raises",0,0,0),
        ("legend_dbox","dashed box = Protocol / abstract base",0,0,0),
        ("legend_sat","satellite (right of a box) = class used only by that box",0,0,0),
        ("legend_cols","Columns: Client → Endpoint/App → Service → Repository/Writer → Source/Models",0,0,2)]

def build():
    ly = 860  # clear lower-left area, below the Client column and clear of all lanes
    parts=['<mxfile host="drawio-plugin" modified="2026-08-31T00:00:00.000Z" agent="claude-code" version="20.5.3" etag="getgit-v030-arch3" type="embed">'
           '<diagram name="Architecture" id="getgit-arch">'
           '<mxGraphModel dx="982" dy="724" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2560" pageHeight="1560" math="0" shadow="0">'
           '<root><mxCell id="0"/><mxCell id="1" parent="0"/>']
    hdrs=[("hdr-client","Client",60,200),("hdr-endpoint","Endpoint / Application",480,240),
          ("hdr-service","Service",900,220),("hdr-repo","Repository / Writer",1320,220),
          ("hdr-source","Source / Models",1920,220)]
    for hid,label,x,w in hdrs:
        parts.append(f'<mxCell id="{hid}" value="{label}" style="text;align=center;fontSize=20;fontStyle=1;" parent="1" vertex="1"><mxGeometry x="{x}" width="{w}" height="40" as="geometry"/></mxCell>')
    for bid,b in BOX.items(): parts.append(box_xml(bid,b))
    for i,(tid,val,fs,bold,ital) in enumerate(LEGEND):
        st=f"text;align=left;fontSize={fs or 12};"+("fontStyle=1;" if bold else ("fontStyle=2;" if ital else ""))
        parts.append(f'<mxCell id="{tid}" value="{html.escape(val)}" style="{st}" parent="1" vertex="1"><mxGeometry x="60" y="{ly+i*26}" width="640" height="22" as="geometry"/></mxCell>')
    for eid,s,t,d in EDGES: parts.append(edge_xml(eid,s,t,d))
    parts.append('</root></mxGraphModel></diagram></mxfile>')
    return "".join(parts)

if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}  ({len(BOX)} boxes, {len(EDGES)} edges)")
