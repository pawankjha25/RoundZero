"use client";

// Round-type -> workspace component lookup. Unmapped/unknown round types fall
// back to ConversationalWorkspace (today's exact text-chat behavior), so a
// new round_type added on the backend never breaks the interview page - it
// just doesn't get a dedicated panel until it's added here.
import CodingWorkspace from "./CodingWorkspace";
import ConversationalWorkspace, { type WorkspaceProps } from "./ConversationalWorkspace";
import MLDepthWorkspace from "./MLDepthWorkspace";
import SystemDesignWorkspace from "./SystemDesignWorkspace";

const CODING_ROUND_TYPES = new Set(["coding", "ml_coding", "ai_assisted_coding"]);
const SYSTEM_DESIGN_ROUND_TYPES = new Set(["ml_system_design", "backend_system_design"]);
const ML_DEPTH_ROUND_TYPES = new Set(["ml_depth"]);

export default function WorkspaceRouter(props: WorkspaceProps) {
  const roundType = props.round.round_type;

  if (CODING_ROUND_TYPES.has(roundType)) {
    return <CodingWorkspace {...props} />;
  }
  if (SYSTEM_DESIGN_ROUND_TYPES.has(roundType)) {
    return <SystemDesignWorkspace {...props} />;
  }
  if (ML_DEPTH_ROUND_TYPES.has(roundType)) {
    return <MLDepthWorkspace {...props} />;
  }
  return <ConversationalWorkspace {...props} />;
}
