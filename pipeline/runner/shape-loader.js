// shape-loader.js — reads pipeline/shapes/<shape>/shape.yaml and exposes
// stage definitions to the rest of the runner.

import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

export class Shape {
  constructor(spec, baseDir) {
    this.spec = spec;
    this.baseDir = baseDir;  // absolute path to pipeline/shapes/<shape>/
    this.id = spec.shape;
    this.displayName = spec.display_name;
    this.stages = spec.stages;
    this.locks = spec.locks || [];
    this.celebration = spec.celebration || null;
    this.watchdog = spec.watchdog || {
      silent_fallback: true,
      triggers: [
        { no_tokens_for_seconds: 8 },
        { any_error: true },
        { exceeded_max_turns: true },
      ],
    };
  }

  stage(id) {
    const s = this.stages.find((x) => x.id === id);
    if (!s) throw new Error(`stage not found: ${id}`);
    return s;
  }

  /** Absolute path relative to the shape's baseDir. */
  resolve(p) {
    if (!p) return null;
    if (path.isAbsolute(p)) return p;
    return path.join(this.baseDir, p);
  }
}

export function loadShape(shapesDir, shapeId) {
  const baseDir = path.join(shapesDir, shapeId);
  const yamlPath = path.join(baseDir, "shape.yaml");
  if (!fs.existsSync(yamlPath)) {
    throw new Error(`shape.yaml not found at ${yamlPath}`);
  }
  const raw = fs.readFileSync(yamlPath, "utf8");
  const spec = yaml.load(raw);
  if (!spec || !spec.stages || !Array.isArray(spec.stages)) {
    throw new Error(`shape.yaml malformed at ${yamlPath}`);
  }
  return new Shape(spec, baseDir);
}
