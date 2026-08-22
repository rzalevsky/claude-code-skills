#!/usr/bin/env python3
"""Turn a small JSON process spec into BPMN 2.0 XML with layout, openable in Camunda Modeler.

The reason this script exists: writing BPMN semantics by hand is easy, writing the
BPMNDI (diagram interchange) block by hand is miserable. Without DI a modeller opens
the file and shows an empty canvas, which reads as "the file is broken" even though
the semantics are fine. So the spec below carries meaning only, and coordinates are
computed here.

Spec format (JSON):
{
  "id": "invoice_intake",
  "name": "Obsluga faktur przychodzacych",
  "lanes": [{"id": "ap", "name": "Ksiegowosc"}, {"id": "mgr", "name": "Kierownik"}],
  "elements": [
    {"id": "start", "type": "startEvent",       "name": "Faktura wplywa", "lane": "ap"},
    {"id": "t1",    "type": "serviceTask",      "name": "Odczyt pol",     "lane": "ap"},
    {"id": "g1",    "type": "exclusiveGateway", "name": "Kwota > 5000?",  "lane": "ap"},
    {"id": "t2",    "type": "userTask",         "name": "Akceptacja",     "lane": "mgr"},
    {"id": "end",   "type": "endEvent",         "name": "Zaksiegowano",   "lane": "ap"}
  ],
  "flows": [
    {"from": "start", "to": "t1"},
    {"from": "t1",    "to": "g1"},
    {"from": "g1",    "to": "t2",  "name": "tak"},
    {"from": "g1",    "to": "end", "name": "nie"},
    {"from": "t2",    "to": "end"}
  ]
}

Supported types: startEvent, endEvent, task, userTask, serviceTask, manualTask,
scriptTask, sendTask, receiveTask, businessRuleTask, exclusiveGateway,
parallelGateway, inclusiveGateway, eventBasedGateway, intermediateCatchEvent,
intermediateThrowEvent, subProcess.

Waiting events carry their kind, because a catch event with no event definition is not
well-formed BPMN:  {"type": "intermediateCatchEvent", "event": "message"}
Kinds: message, timer, signal, error, conditional.

Not supported, deliberately: boundaryEvent (needs attachedToRef) and pools/message flows
(need a collaboration). Model a deadline as an exclusive gateway after the task, and
another organisation as an event this process waits for.

Usage:
    python3 build_bpmn.py spec.json -o process.bpmn --check-layout
    python3 build_bpmn.py spec.json --validate-only
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, deque

EVENTS = {"startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent"}
# boundaryEvent is deliberately NOT supported: it needs attachedToRef and has no incoming
# flow, which this generator's layout and validation model cannot express. Use an
# exclusive gateway after the task instead, and say in the notes that it is a simplification.
UNSUPPORTED = {"boundaryEvent", "participant", "messageFlow"}
EVENT_DEFINITIONS = {"message": "messageEventDefinition", "timer": "timerEventDefinition",
                     "signal": "signalEventDefinition", "error": "errorEventDefinition",
                     "conditional": "conditionalEventDefinition"}
GATEWAYS = {"exclusiveGateway", "parallelGateway", "inclusiveGateway", "eventBasedGateway",
            "complexGateway"}
TASKS = {"task", "userTask", "serviceTask", "manualTask", "scriptTask", "sendTask",
         "receiveTask", "businessRuleTask", "callActivity", "subProcess"}
KNOWN = EVENTS | GATEWAYS | TASKS

# Geometry. Chosen so a printed model stays legible rather than to fill the canvas.
EVENT_SIZE = 36
GATEWAY_SIZE = 50
TASK_W, TASK_H = 140, 80
RANK_GAP = 90          # horizontal space between columns
ROW_GAP = 30           # vertical space between elements in the same column
LANE_PAD = 20          # padding inside a lane band
LANE_LABEL_W = 30      # width of the rotated lane name strip
ORIGIN_X, ORIGIN_Y = 160, 80

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
}


class SpecError(Exception):
    """The spec is wrong in a way the author has to fix; the message says how."""


def size_of(kind: str) -> tuple[int, int]:
    if kind in EVENTS:
        return EVENT_SIZE, EVENT_SIZE
    if kind in GATEWAYS:
        return GATEWAY_SIZE, GATEWAY_SIZE
    return TASK_W, TASK_H


def validate(spec: dict) -> list[str]:
    """Return a list of problems. Empty list means the spec is structurally sound."""
    problems: list[str] = []
    elements = spec.get("elements") or []
    flows = spec.get("flows") or []
    if not elements:
        return ["No elements. A process with no elements is not a diagram."]

    ids = [e.get("id") for e in elements]
    for dup in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"Duplicate element id: {dup}")
    for element in elements:
        if not element.get("id"):
            problems.append(f"Element without id: {element}")
        kind = element.get("type")
        if kind in UNSUPPORTED:
            problems.append(
                f"'{kind}' on '{element.get('id')}' is not supported by this generator. "
                f"Boundary events need attachedToRef, and pools/message flows need a "
                f"collaboration - neither fits this layout model. Model a deadline as an "
                f"exclusive gateway after the task, and another organisation as an event "
                f"the process waits for. Note the simplification next to the diagram.")
        elif kind not in KNOWN:
            problems.append(f"Unknown type '{kind}' on '{element.get('id')}'. "
                            f"Known: {', '.join(sorted(KNOWN))}")
        event = element.get("event")
        if event and event not in EVENT_DEFINITIONS:
            problems.append(f"Unknown event kind '{event}' on '{element.get('id')}'. "
                            f"Known: {', '.join(sorted(EVENT_DEFINITIONS))}")
        if kind in ("intermediateCatchEvent", "intermediateThrowEvent") and not event:
            problems.append(
                f"'{element.get('id')}' is a {kind} with no \"event\" kind. A catch event "
                f"with no event definition is not well-formed BPMN - modellers draw a bare "
                f"double circle and validators flag it. Add \"event\": \"message\" or \"timer\".")

    known_ids = set(ids)
    lane_ids = {lane["id"] for lane in spec.get("lanes", [])}
    for element in elements:
        lane = element.get("lane")
        if lane and lane not in lane_ids:
            problems.append(f"Element '{element['id']}' points at lane '{lane}', which is not declared.")

    for flow in flows:
        for end in ("from", "to"):
            if flow.get(end) not in known_ids:
                problems.append(f"Flow {flow.get('from')} -> {flow.get('to')}: "
                                f"'{flow.get(end)}' is not an element id.")

    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for flow in flows:
        outgoing[flow.get("from")].append(flow)
        incoming[flow.get("to")].append(flow)

    starts = [e for e in elements if e.get("type") == "startEvent"]
    ends = [e for e in elements if e.get("type") == "endEvent"]
    if not starts:
        problems.append("No startEvent. Every process needs a trigger - name what starts it.")
    if not ends:
        problems.append("No endEvent. A process that never ends usually means a missing outcome.")

    for element in elements:
        eid, kind = element.get("id"), element.get("type")
        if kind != "startEvent" and not incoming[eid]:
            problems.append(f"'{eid}' is unreachable - nothing flows into it.")
        if kind != "endEvent" and not outgoing[eid]:
            problems.append(f"'{eid}' is a dead end - nothing flows out of it.")
        if kind in GATEWAYS and len(outgoing[eid]) < 2 and len(incoming[eid]) < 2:
            problems.append(f"Gateway '{eid}' neither splits nor merges. "
                            f"A gateway with one in and one out is noise - delete it.")
        if kind == "exclusiveGateway" and len(outgoing[eid]) > 1:
            unnamed = [f for f in outgoing[eid] if not f.get("name")]
            if unnamed:
                problems.append(f"Exclusive gateway '{eid}' has unlabelled branches. "
                                f"An unlabelled condition is a decision nobody can audit.")
    return problems


def rank_elements(elements: list[dict], flows: list[dict]) -> dict:
    """Longest-path layering: each node sits one column right of its latest predecessor."""
    ids = [e["id"] for e in elements]
    outgoing = defaultdict(list)
    indegree = {i: 0 for i in ids}
    for flow in flows:
        outgoing[flow["from"]].append(flow["to"])
        indegree[flow["to"]] += 1

    rank = {i: 0 for i in ids}
    queue = deque([i for i in ids if indegree[i] == 0]) or deque([ids[0]])
    seen = set(queue)
    processed = 0
    while queue:
        node = queue.popleft()
        processed += 1
        for target in outgoing[node]:
            rank[target] = max(rank[target], rank[node] + 1)
            indegree[target] -= 1
            if indegree[target] <= 0 and target not in seen:
                seen.add(target)
                queue.append(target)
    if processed < len(ids):
        # A loop back to an earlier step is normal in real processes (rework, retry).
        # Nodes the topological pass never reached get placed after their earliest predecessor.
        for element in elements:
            if element["id"] not in seen:
                preds = [f["from"] for f in flows if f["to"] == element["id"] and f["from"] in rank]
                rank[element["id"]] = (min(rank[p] for p in preds) + 1) if preds else 0
    return rank


def layout(spec: dict) -> tuple[dict, list[dict], int, int]:
    elements = spec["elements"]
    flows = spec.get("flows", [])
    lanes = spec.get("lanes") or []
    rank = rank_elements(elements, flows)

    by_id = {e["id"]: e for e in elements}
    lane_order = [lane["id"] for lane in lanes] or [None]
    lane_of = {e["id"]: (e.get("lane") if lanes else None) for e in elements}

    # Column x positions: width of a column is the widest element in it.
    max_rank = max(rank.values()) if rank else 0
    col_width = {}
    for r in range(max_rank + 1):
        widths = [size_of(by_id[i]["type"])[0] for i in rank if rank[i] == r]
        col_width[r] = max(widths) if widths else TASK_W
    col_x, x_cursor = {}, ORIGIN_X
    for r in range(max_rank + 1):
        col_x[r] = x_cursor
        x_cursor += col_width[r] + RANK_GAP
    diagram_width = x_cursor + LANE_PAD

    # Lane band heights: tall enough for the busiest column in that lane.
    lane_height, lane_y = {}, {}
    y_cursor = ORIGIN_Y
    for lane_id in lane_order:
        per_rank = defaultdict(list)
        for element in elements:
            if lane_of[element["id"]] == lane_id:
                per_rank[rank[element["id"]]].append(element)
        busiest = max((sum(size_of(e["type"])[1] for e in group) + ROW_GAP * (len(group) - 1)
                       for group in per_rank.values()), default=TASK_H)
        height = max(busiest + 2 * LANE_PAD, TASK_H + 2 * LANE_PAD)
        lane_y[lane_id] = y_cursor
        lane_height[lane_id] = height
        y_cursor += height
    diagram_height = y_cursor + LANE_PAD

    # Place each element: centred in its column, stacked inside its lane band.
    bounds = {}
    for lane_id in lane_order:
        per_rank = defaultdict(list)
        for element in elements:
            if lane_of[element["id"]] == lane_id:
                per_rank[rank[element["id"]]].append(element)
        for r, group in per_rank.items():
            total = sum(size_of(e["type"])[1] for e in group) + ROW_GAP * (len(group) - 1)
            y = lane_y[lane_id] + (lane_height[lane_id] - total) / 2
            for element in group:
                w, h = size_of(element["type"])
                x = col_x[r] + (col_width[r] - w) / 2
                bounds[element["id"]] = {"x": round(x), "y": round(y), "w": w, "h": h}
                y += h + ROW_GAP

    lane_boxes = [{"id": lane["id"], "name": lane.get("name", ""),
                   "x": ORIGIN_X - LANE_PAD - LANE_LABEL_W, "y": lane_y[lane["id"]],
                   "w": diagram_width - ORIGIN_X + LANE_PAD + LANE_LABEL_W,
                   "h": lane_height[lane["id"]]}
                  for lane in lanes]
    return bounds, lane_boxes, round(diagram_width), round(diagram_height)


def waypoints(src: dict, dst: dict) -> list[tuple[float, float]]:
    """Right edge of source to left edge of target, with one elbow when rows differ."""
    sx, sy = src["x"] + src["w"], src["y"] + src["h"] / 2
    tx, ty = dst["x"], dst["y"] + dst["h"] / 2
    if tx < sx:  # loop back: route under both elements
        below = max(src["y"] + src["h"], dst["y"] + dst["h"]) + ROW_GAP
        return [(src["x"] + src["w"] / 2, src["y"] + src["h"]),
                (src["x"] + src["w"] / 2, below),
                (dst["x"] + dst["w"] / 2, below),
                (dst["x"] + dst["w"] / 2, dst["y"] + dst["h"])]
    if abs(sy - ty) < 1:
        return [(sx, sy), (tx, ty)]
    mid = (sx + tx) / 2
    return [(sx, sy), (mid, sy), (mid, ty), (tx, ty)]


def build_xml(spec: dict) -> str:
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)

    process_id = spec.get("id", "Process_1")
    bounds, lane_boxes, width, height = layout(spec)

    definitions = ET.Element(f"{{{NS['bpmn']}}}definitions", {
        "id": f"Definitions_{process_id}",
        "targetNamespace": "http://bpmn.io/schema/bpmn",
        "exporter": "bpmn-from-prose",
        "exporterVersion": "1.0",
    })
    process = ET.SubElement(definitions, f"{{{NS['bpmn']}}}process", {
        "id": process_id,
        "name": spec.get("name", process_id),
        "isExecutable": "false",
    })

    if spec.get("lanes"):
        lane_set = ET.SubElement(process, f"{{{NS['bpmn']}}}laneSet", {"id": f"LaneSet_{process_id}"})
        for lane in spec["lanes"]:
            node = ET.SubElement(lane_set, f"{{{NS['bpmn']}}}lane",
                                 {"id": lane["id"], "name": lane.get("name", "")})
            for element in spec["elements"]:
                if element.get("lane") == lane["id"]:
                    ref = ET.SubElement(node, f"{{{NS['bpmn']}}}flowNodeRef")
                    ref.text = element["id"]

    flows = spec.get("flows", [])
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for index, flow in enumerate(flows):
        flow.setdefault("id", f"Flow_{index + 1}")
        outgoing[flow["from"]].append(flow["id"])
        incoming[flow["to"]].append(flow["id"])

    for element in spec["elements"]:
        node = ET.SubElement(process, f"{{{NS['bpmn']}}}{element['type']}",
                             {"id": element["id"], "name": element.get("name", "")})
        for flow_id in incoming[element["id"]]:
            ET.SubElement(node, f"{{{NS['bpmn']}}}incoming").text = flow_id
        for flow_id in outgoing[element["id"]]:
            ET.SubElement(node, f"{{{NS['bpmn']}}}outgoing").text = flow_id
        event = element.get("event")
        if event in EVENT_DEFINITIONS:
            ET.SubElement(node, f"{{{NS['bpmn']}}}{EVENT_DEFINITIONS[event]}",
                          {"id": f"{element['id']}_def"})

    for flow in flows:
        attrs = {"id": flow["id"], "sourceRef": flow["from"], "targetRef": flow["to"]}
        if flow.get("name"):
            attrs["name"] = flow["name"]
        ET.SubElement(process, f"{{{NS['bpmn']}}}sequenceFlow", attrs)

    diagram = ET.SubElement(definitions, f"{{{NS['bpmndi']}}}BPMNDiagram", {"id": "Diagram_1"})
    plane = ET.SubElement(diagram, f"{{{NS['bpmndi']}}}BPMNPlane",
                          {"id": "Plane_1", "bpmnElement": process_id})

    for lane in lane_boxes:
        shape = ET.SubElement(plane, f"{{{NS['bpmndi']}}}BPMNShape",
                              {"id": f"{lane['id']}_di", "bpmnElement": lane["id"],
                               "isHorizontal": "true"})
        ET.SubElement(shape, f"{{{NS['dc']}}}Bounds",
                      {k: str(int(v)) for k, v in
                       zip(("x", "y", "width", "height"),
                           (lane["x"], lane["y"], lane["w"], lane["h"]))})

    for element in spec["elements"]:
        box = bounds[element["id"]]
        attrs = {"id": f"{element['id']}_di", "bpmnElement": element["id"]}
        if element["type"] in GATEWAYS or element["type"] in EVENTS:
            attrs["isMarkerVisible"] = "true" if element["type"] == "exclusiveGateway" else "false"
        shape = ET.SubElement(plane, f"{{{NS['bpmndi']}}}BPMNShape", attrs)
        ET.SubElement(shape, f"{{{NS['dc']}}}Bounds",
                      {"x": str(box["x"]), "y": str(box["y"]),
                       "width": str(box["w"]), "height": str(box["h"])})
        if element.get("name") and element["type"] in EVENTS | GATEWAYS:
            label = ET.SubElement(shape, f"{{{NS['bpmndi']}}}BPMNLabel")
            ET.SubElement(label, f"{{{NS['dc']}}}Bounds",
                          {"x": str(box["x"] - 20), "y": str(box["y"] + box["h"] + 6),
                           "width": "90", "height": "27"})

    for flow in flows:
        edge = ET.SubElement(plane, f"{{{NS['bpmndi']}}}BPMNEdge",
                             {"id": f"{flow['id']}_di", "bpmnElement": flow["id"]})
        for x, y in waypoints(bounds[flow["from"]], bounds[flow["to"]]):
            ET.SubElement(edge, f"{{{NS['di']}}}waypoint", {"x": str(int(x)), "y": str(int(y))})

    ET.indent(definitions, space="  ")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(definitions, encoding="unicode"))


def check_layout(spec: dict) -> list:
    """Report layout problems a reviewer would spot instantly but an agent cannot see.

    Generated BPMN can validate perfectly and still read badly - most often when a task is
    joined from a late branch, which the longest-path ranking pushes far to the right and
    leaves a long edge threading past unrelated shapes.
    """
    bounds, lane_boxes, width, height = layout(spec)
    notes = []

    items = list(bounds.items())
    for i, (id_a, a) in enumerate(items):
        for id_b, b in items[i + 1:]:
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                notes.append(f"OVERLAP: '{id_a}' and '{id_b}' occupy the same space.")

    for lane in lane_boxes:
        for element in spec["elements"]:
            if element.get("lane") != lane["id"]:
                continue
            box = bounds[element["id"]]
            if box["y"] < lane["y"] or box["y"] + box["h"] > lane["y"] + lane["h"]:
                notes.append(f"OUT OF LANE: '{element['id']}' sits outside '{lane['id']}'.")

    for flow in spec.get("flows", []):
        src, dst = bounds[flow["from"]], bounds[flow["to"]]
        span = dst["x"] - (src["x"] + src["w"])
        if span > RANK_GAP * 3:
            notes.append(
                f"LONG EDGE: {flow['from']} -> {flow['to']} spans {int(span)}px. "
                f"Usually a task joined from a late branch. If the two paths reach genuinely "
                f"different work, duplicate the task; if not, it is cosmetic.")

    if not notes:
        notes.append(f"Layout clean: no overlaps, nothing outside its lane, no stretched "
                     f"edges. Canvas {width}x{height}px.")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", help="path to the JSON spec")
    parser.add_argument("-o", "--out", help="output .bpmn path (default: <spec id>.bpmn)")
    parser.add_argument("--validate-only", action="store_true",
                        help="report structural problems and stop")
    parser.add_argument("--check-layout", action="store_true",
                        help="after generating, report overlapping shapes and over-stretched "
                             "flows - the layout problems you cannot see without a modeller")
    args = parser.parse_args()

    with open(args.spec, encoding="utf-8") as handle:
        spec = json.load(handle)

    problems = validate(spec)
    # Advisory problems are modelling-quality notes: the file still generates, because a
    # half-modelled process is often exactly what you want to put in front of a process
    # owner to argue about. Everything else stops generation.
    ADVISORY = ("neither splits nor merges", "unlabelled branches", "No endEvent")
    if problems:
        blocking = [p for p in problems if not any(a in p for a in ADVISORY)]
        advisory = [p for p in problems if p not in blocking]
        if blocking:
            print("BLOCKING problems - no file written:", file=sys.stderr)
            for problem in blocking:
                print(f"  - {problem}", file=sys.stderr)
        if advisory:
            print("Modelling-quality notes (file still generated):", file=sys.stderr)
            for problem in advisory:
                print(f"  - {problem}", file=sys.stderr)
        if blocking:
            return 1
        if args.validate_only:
            return 0
    elif args.validate_only:
        print("Spec is structurally sound.\n"
              "Not checked here: whether the model matches reality, whether the exceptions "
              "are present, and whether the layout reads well. Run --check-layout after "
              "generating, and have the process owner read the diagram.")
        return 0

    xml = build_xml(spec)
    out = args.out or f"{spec.get('id', 'process')}.bpmn"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(xml)
    print(f"Wrote {out} ({len(spec['elements'])} elements, {len(spec.get('flows', []))} flows).")
    if args.check_layout:
        print()
        for line in check_layout(spec):
            print(line)
    else:
        print("Open it in Camunda Modeler to check the layout, or run --check-layout if you "
              "cannot open a modeller here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
