import assert from "node:assert/strict";
import test from "node:test";
import { findNearestCell, parseCoordinates, type LookupGrid } from "../components/lookup";

const schema = ["lon", "lat", "priority", "class", "airstrike_score", "crater_score", "airstrike_records", "craters", "craters_300m"];
const strict: LookupGrid = {schema, class_labels: ["Cao"], cell_ids: ["GRID100_C000_R000"], rows: [[106.95, 16.8, .7, 0, .6, .8, 1, 2, 3]]};

test("reject missing, non-finite and impossible coordinates", () => {
  for (const [lat, lon] of [["", "106.95"], [" ", "106.95"], ["16.8", ""], ["100", "106.95"], ["16.8", "181"], ["NaN", "106.95"], ["Infinity", "0"]]) {
    assert.throws(() => parseCoordinates(lat, lon));
  }
  assert.deepEqual(parseCoordinates("16.8", "106.95"), {lat: 16.8, lon: 106.95});
});

test("keep strict-real cell IDs and reject positions outside the analysis area", () => {
  assert.equal(findNearestCell(strict, 16.8, 106.95).cellId, "GRID100_C000_R000");
  assert.throws(() => findNearestCell(strict, 0, 0), /ngoài vùng/);
});

test("support the existing bundled UTM lookup schema", () => {
  const legacy = {...strict, cell_ids: undefined, schema: [...schema, "e", "n"], rows: [[...strict.rows[0], 7078, 18584]]};
  assert.equal(findNearestCell(legacy, 16.8, 106.95).cellId, "U48N_100_E7078_N18584");
});

test("select nearest cell by physical distance, not squared degrees", () => {
  const data: LookupGrid = {schema, class_labels: ["Cao"], cell_ids: ["east", "north"], rows: [
    [106.9505, 16.8, .7, 0, .6, .8, 1, 2, 3],
    [106.95, 16.80049, .6, 0, .5, .7, 1, 2, 3],
  ]};
  assert.equal(findNearestCell(data, 16.8, 106.95).cellId, "east");
});

test("reject an empty grid or missing cell identity", () => {
  assert.throws(() => findNearestCell({...strict, rows: []}, 16.8, 106.95));
  assert.throws(() => findNearestCell({...strict, cell_ids: undefined}, 16.8, 106.95), /mã ô/);
});
