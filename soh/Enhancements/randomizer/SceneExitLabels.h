#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <numeric>
#include <utility>
#include <vector>

namespace SohExtreme {

struct ExitPoint { float x, y, z; };
struct ExitTriangle { int exit; std::array<ExitPoint, 3> points; int polygon = -1; };
struct ExitAnchor { int exit; ExitPoint position; std::vector<int> polygons; };

// Each connected trigger gets its own label. Separate passages may use the
// same exit-list entry; averaging those together would put text between them.
inline std::vector<ExitAnchor> SceneExitAnchors(const std::vector<ExitTriangle>& triangles) {
    std::vector<size_t> parent(triangles.size());
    std::iota(parent.begin(), parent.end(), 0);
    const auto root = [&](size_t i) {
        while (parent[i] != i) { parent[i] = parent[parent[i]]; i = parent[i]; }
        return i;
    };
    std::map<std::array<float, 4>, size_t> vertices;
    for (size_t i = 0; i < triangles.size(); ++i) {
        for (const auto& p : triangles[i].points) {
            const auto [it, inserted] = vertices.emplace(
                std::array<float, 4>{ static_cast<float>(triangles[i].exit), p.x, p.y, p.z }, i);
            if (!inserted) parent[root(i)] = root(it->second);
        }
    }
    struct Group { double x = 0, y = 0, z = 0, weight = 0; std::vector<size_t> members; };
    std::map<size_t, Group> groups;
    std::vector<ExitPoint> centers;
    for (size_t i = 0; i < triangles.size(); ++i) {
        const auto& p = triangles[i].points;
        const double ax = p[1].x-p[0].x, ay = p[1].y-p[0].y, az = p[1].z-p[0].z;
        const double bx = p[2].x-p[0].x, by = p[2].y-p[0].y, bz = p[2].z-p[0].z;
        const double cx = ay*bz-az*by, cy = az*bx-ax*bz, cz = ax*by-ay*bx;
        const double weight = std::max(1.0, std::sqrt(cx*cx+cy*cy+cz*cz));
        const ExitPoint center{ (p[0].x+p[1].x+p[2].x)/3,
                                (p[0].y+p[1].y+p[2].y)/3, (p[0].z+p[1].z+p[2].z)/3 };
        centers.push_back(center);
        auto& group = groups[root(i)];
        group.x += center.x*weight; group.y += center.y*weight; group.z += center.z*weight;
        group.weight += weight; group.members.push_back(i);
    }
    std::vector<ExitAnchor> result;
    for (const auto& [id, group] : groups) {
        // Pick a triangle center near the weighted center, keeping the label on
        // the trigger even for an L-shaped or otherwise concave exit surface.
        size_t nearest = group.members.front();
        double best = -1;
        for (size_t i : group.members) {
            const auto& p = centers[i];
            const double dx = p.x-group.x/group.weight, dy = p.y-group.y/group.weight,
                         dz = p.z-group.z/group.weight;
            const double distance = dx*dx+dy*dy+dz*dz;
            if (best < 0 || distance < best) { best = distance; nearest = i; }
        }
        ExitAnchor anchor{ triangles[nearest].exit, centers[nearest], {} };
        // Preserve physical ownership for a door's native scene-exit probe.
        for (size_t i : group.members) {
            if (triangles[i].polygon >= 0) anchor.polygons.push_back(triangles[i].polygon);
        }
        result.push_back(std::move(anchor));
    }
    return result;
}

// Same grouping used by Player_HandleExitsAndVoids, with bounds checks for
// debugging a partially loaded scene. Return the dynamicExitList index.
inline int SceneDynamicExitIndex(int entrance, int spawn) {
    constexpr int starts[] = { 11, 9, 3, 5, 7, 0 };
    constexpr int lengths[] = { 3, 2, 2, 2, 2, 3 };
    const int group = entrance - 0x7FF9;
    return group >= 0 && group < 6 && spawn >= 0 && spawn < lengths[group] ? starts[group]+spawn : -1;
}

} // namespace SohExtreme
