// Converts an Excalidraw scene into a compact, semantic text summary for the
// interviewer's context - never the raw element JSON (per the workspace spec:
// "Do not send every mouse movement to the LLM. Debounce meaningful canvas
// changes and convert the Excalidraw scene into a compact semantic
// representation"). Called client-side from SystemDesignWorkspace on a
// debounced onChange; the resulting string is what gets sent to
// saveCanvas/orchestrator.py's workspace_context, not the scene itself.
//
// Minimal structural subset of Excalidraw's element type - avoids taking a
// direct type dependency on @excalidraw/excalidraw's internal element types,
// which are intentionally broad (unions of many shape kinds) and change
// across versions.
export interface SceneElementLike {
  id: string;
  type: string;
  text?: string;
  containerId?: string | null;
  startBinding?: { elementId: string } | null;
  endBinding?: { elementId: string } | null;
  isDeleted?: boolean;
}

const SHAPE_TYPES = new Set(["rectangle", "diamond", "ellipse"]);

export function summarizeScene(elements: SceneElementLike[]): string {
  const live = elements.filter((el) => !el.isDeleted);

  // containerId -> bound text, so a labeled rectangle becomes e.g. "API Gateway"
  // instead of "rectangle (a1b2c3)".
  const textByContainer = new Map<string, string>();
  for (const el of live) {
    if (el.type === "text" && el.containerId) {
      const existing = textByContainer.get(el.containerId);
      const piece = (el.text ?? "").trim();
      if (piece) {
        textByContainer.set(el.containerId, existing ? `${existing} ${piece}` : piece);
      }
    }
  }

  const shapeNames = new Map<string, string>();
  const components: string[] = [];
  for (const el of live) {
    if (!SHAPE_TYPES.has(el.type)) continue;
    const label = textByContainer.get(el.id);
    const name = label && label.length > 0 ? label : `${el.type} (unlabeled)`;
    shapeNames.set(el.id, name);
    components.push(name);
  }

  const edges: string[] = [];
  for (const el of live) {
    if (el.type !== "arrow") continue;
    const startId = el.startBinding?.elementId;
    const endId = el.endBinding?.elementId;
    if (!startId || !endId) continue; // unbound arrow endpoint - nothing semantic to name
    const startName = shapeNames.get(startId);
    const endName = shapeNames.get(endId);
    if (startName && endName) {
      edges.push(`${startName} → ${endName}`);
    }
  }

  // Freestanding text (not bound to a shape) - kept as a note rather than
  // dropped, e.g. a candidate jotting "cache TTL = 5min" off to the side.
  const notes: string[] = [];
  for (const el of live) {
    if (el.type === "text" && !el.containerId) {
      const piece = (el.text ?? "").trim();
      if (piece) notes.push(piece);
    }
  }

  if (components.length === 0 && edges.length === 0 && notes.length === 0) {
    return "";
  }

  const parts: string[] = [];
  if (components.length > 0) parts.push(`Components: ${components.join(", ")}`);
  if (edges.length > 0) parts.push(`Flow: ${edges.join("; ")}`);
  if (notes.length > 0) parts.push(`Notes: ${notes.join("; ")}`);
  return parts.join("\n");
}
