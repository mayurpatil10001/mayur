#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const mapPath = path.join(__dirname, '..', 'node_modules', 'plotly.js', 'dist', 'maplibre-gl-unminified.js.map');
const dir = path.dirname(mapPath);
if (!fs.existsSync(mapPath)) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(mapPath, '{"version":3,"sources":[],"names":[],"mappings":""}');
  console.log('Created missing plotly.js source map:', mapPath);
}
