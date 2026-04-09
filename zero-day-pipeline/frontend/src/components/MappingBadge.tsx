// Colored badge indicating the mapping status of a KEV entry:
// green for registry match, purple for Claude-assisted, gray for unmappable.

import type { MappingStatus } from "../types";

interface Props {
  status: MappingStatus;
}

const CONFIG: Record<MappingStatus, { label: string; className: string }> = {
  mapped: { label: "Registry match", className: "mapping-badge mapping-badge-mapped" },
  claude_assisted: { label: "Claude-assisted", className: "mapping-badge mapping-badge-claude" },
  unmappable: { label: "Unmappable", className: "mapping-badge mapping-badge-unmappable" },
};

export default function MappingBadge({ status }: Props) {
  const c = CONFIG[status];
  return <span className={c.className}>{c.label}</span>;
}
