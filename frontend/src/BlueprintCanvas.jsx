import React from "react";
import { Stage, Layer, Rect, Circle, Text, Line } from "react-konva";

const TILE = 44;
const TERRAIN = { grass: "#8fce7a", sand: "#ecdca0", water: "#6fb7e8", cliff: "#8a7a63", building: "#c96f5a", unknown: "#cfcfcf" };
const CATEGORY = { path: "#d9c7a3", flower: "#ff7fa8", tree: "#2f7d32", furniture: "#7a5cc4" };

function footprint(item, p) {
  const rotated = p.rotation === 90 || p.rotation === 270;
  return { w: rotated ? item.height : item.width, h: rotated ? item.width : item.height };
}

// 설계도(구조화 데이터)를 2D 격자로 그린다. 이미지 생성 결과가 아니라 JSON을 그대로 표시한다.
export default function BlueprintCanvas({ zone, design, catalog, plan }) {
  const items = Object.fromEntries(catalog.map((i) => [i.id, i]));
  const placements = design ? design.placements : [];
  const ground = placements.filter((p) => items[p.item_id]?.layer === "ground");
  const objects = placements.filter((p) => items[p.item_id]?.layer === "object");
  const route = plan
    ? [zone.start, ...plan.tasks.flatMap((t) => t.path)].flatMap(([x, y]) => [x * TILE + TILE / 2, y * TILE + TILE / 2])
    : [];

  return (
    <Stage width={zone.width * TILE} height={zone.height * TILE}>
      <Layer>
        {zone.tiles.flatMap((row, y) =>
          row.map((t, x) => (
            <Rect key={`${x}-${y}`} x={x * TILE} y={y * TILE} width={TILE} height={TILE}
                  fill={TERRAIN[t]} stroke="#00000022" strokeWidth={1} />
          ))
        )}
        {ground.map((p, i) => (
          <Rect key={`g${i}`} x={p.x * TILE + 3} y={p.y * TILE + 3} width={TILE - 6} height={TILE - 6}
                fill={CATEGORY.path} cornerRadius={6} />
        ))}
        {route.length > 2 && <Line points={route} stroke="#00000055" strokeWidth={2} dash={[6, 6]} />}
        {objects.map((p, i) => {
          const item = items[p.item_id];
          const { w, h } = footprint(item, p);
          const color = CATEGORY[item.category];
          return item.category === "furniture" ? (
            <Rect key={`o${i}`} x={p.x * TILE + 6} y={p.y * TILE + 6} width={w * TILE - 12} height={h * TILE - 12}
                  fill={color} cornerRadius={4} />
          ) : (
            <Circle key={`o${i}`} x={p.x * TILE + TILE / 2} y={p.y * TILE + TILE / 2}
                    radius={item.category === "tree" ? 16 : 9} fill={color} />
          );
        })}
        <Text x={zone.start[0] * TILE} y={zone.start[1] * TILE + 14} width={TILE} align="center"
              text="S" fontStyle="bold" fontSize={16} />
      </Layer>
    </Stage>
  );
}
