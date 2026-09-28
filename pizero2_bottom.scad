// ==========================================
// Raspberry Pi Zero 2 W - Bento Box (Bottom) - 3.0mm Box Floor & 1.0mm Flat Handler
// ==========================================

pi_w = 65.0; 
pi_d = 30.0; 
pi_h = 1.6;  

thickness       = 1.0;    // 周囲の壁の厚み (1.0mm)
floor_thickness = 3.0;    // ボックス本体の底面プレートの厚み (3.0mm)
clearance       = 1.0;    // 基板とケース内壁の隙間
box_h           = 9.5;    // 全高 (内部コンポーネント空間5.5mmをキープ)

inner_w = 69.0 + (clearance * 2); 
inner_d = pi_d + (clearance * 2);
outer_w = inner_w + (thickness * 2);

// 全体の奥行き（Y軸）の外寸を 40mm に固定
outer_d = 40.0; 

// ボックス本体（立ち上がり壁があるエリア）の奥行き外寸
box_outer_d = inner_d + (thickness * 2);

hole_dx = 58.0;     
hole_dy = 23.0;     
post_r  = 2.2;      
screw_r = 1.3;      
post_h  = 1.5;      

$fn = 32;

main_box();

module main_box() {
    difference() {
        union() {
            // 1. 基板が収まるボックス本体（手前側に配置：底面は3.0mm厚になります）
            cube([outer_w, box_outer_d, box_h]);
            
            // 2. 🛠️【アップデート】奥側に突き出すフラットなハンドラー部分は「1.0mm厚」をキープ！
            translate([0, box_outer_d, 0])
                cube([outer_w, outer_d - box_outer_d, 1.0]);
            
            // 全ボスの基準位置をボックスの底面厚 (floor_thickness) の上に配置
            translate([thickness + clearance, thickness + clearance, floor_thickness]) {
                offset_x = ((inner_w - 4.0) - hole_dx) / 2;
                offset_y = (inner_d - hole_dy) / 2;
                translate([offset_x, offset_y, 0]) post_group();
            }
        }
        
        // 内側のくり抜き（開始高さを floor_thickness に変更）
        translate([thickness, thickness, floor_thickness])
            cube([inner_w, inner_d, box_h]);
        
        // ネジ下穴の引き算処理
        translate([thickness + clearance, thickness + clearance, 0]) {
            offset_x = ((inner_w - 4.0) - hole_dx) / 2;
            offset_y = (inner_d - hole_dy) / 2;
            translate([offset_x, offset_y, -0.5]) hole_group(h = box_h);
        }
        
        // 📷 左側面窓：底面の高さに合わせてZ軸開始位置を同期
        translate([-0.5, box_outer_d / 2 - 10.5, floor_thickness + post_h - 1.0])
            cube([thickness + 1, 21, 5.5]);

        // 🔲 右側面窓：底面の高さに合わせてZ軸開始位置を同期
        translate([outer_w - thickness - 0.5, box_outer_d / 2 - 10.5, floor_thickness + post_h - 1.0])
            cube([thickness + 1, 21, 5.5]);

        // 🔌 手前側の端子用切り欠き（HDMI/USB用）
        translate([thickness + clearance + 5, -0.5, (floor_thickness + post_h + pi_h) - 2.0])
            cube([pi_w - 10, thickness + 1, box_h]);

        // 🧵 🛠️【アップデート】マジックバンド固定用の貫通スリット窓
        // ハンドラー部分の厚み（1.0mm）に合わせて引き算の深さを最適化（-0.5から2.0mmまでカット）
        // 左側のスリット穴
        translate([thickness + 4, outer_d - thickness - 4.0, -0.5]) 
            cube([16, 2.5, 2.0]);
            
        // 右側のスリット穴
        translate([outer_w - thickness - 20, outer_d - thickness - 4.0, -0.5]) 
            cube([16, 2.5, 2.0]);
    }
}

module post_group() {
    cylinder(r = post_r, h = post_h);
    translate([hole_dx, 0, 0]) cylinder(r = post_r, h = post_h);
    translate([0, hole_dy, 0]) cylinder(r = post_r, h = post_h);
    translate([hole_dx, hole_dy, 0]) cylinder(r = post_r, h = post_h);
}

module hole_group(h) {
    cylinder(r = screw_r, h = h);
    translate([hole_dx, 0, 0]) cylinder(r = screw_r, h = h);
    translate([0, hole_dy, 0]) cylinder(r = screw_r, h = h);
    translate([hole_dx, hole_dy, 0]) cylinder(r = screw_r, h = h);
}
