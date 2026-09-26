// ==========================================
// Raspberry Pi Zero 2 W - Bento Box (Bottom) - Flat Handler with Magic Band Slits
// ==========================================

pi_w = 65.0; 
pi_d = 30.0; 
pi_h = 1.6;  

thickness = 1.0;    
clearance = 1.0;    
box_h     = 7.5;    // 6mm高に合わせた超ロープロファイル仕様

inner_w = 69.0 + (clearance * 2); 
inner_d = pi_d + (clearance * 2);
outer_w = inner_w + (thickness * 2);

// 🛠️ 【アップデート】全体の奥行き（Y軸）の外寸を 40mm に固定
outer_d = 40.0; 

// ボックス本体（立ち上がり壁があるエリア）の奥行き外寸を計算
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
            // 1. 基板が収まるボックス本体（手前側に配置）
            cube([outer_w, box_outer_d, box_h]);
            
            // 2. 🛠️ 【アップデート】奥側に突き出すフラットなハンドラー部分（底面と同じ1.0mm厚）
            translate([0, box_outer_d, 0])
                cube([outer_w, outer_d - box_outer_d, thickness]);
            
            // スタンドオフ
            translate([thickness + clearance, thickness + clearance, thickness]) {
                offset_x = ((inner_w - 4.0) - hole_dx) / 2;
                offset_y = (inner_d - hole_dy) / 2;
                translate([offset_x, offset_y, 0]) post_group();
            }
        }
        
        // 内側のくり抜き（ボックス本体のエリアのみ）
        translate([thickness, thickness, thickness])
            cube([inner_w, inner_d, box_h]);
        
        // ネジ下穴
        translate([thickness + clearance, thickness + clearance, 0]) {
            offset_x = ((inner_w - 4.0) - hole_dx) / 2;
            offset_y = (inner_d - hole_dy) / 2;
            translate([offset_x, offset_y, -0.5]) hole_group(h = box_h);
        }
        
        // 📷 【左側面】CSIカメラケーブル用スリット窓（位置を基板エリアの中心に補正）
        translate([-0.5, box_outer_d / 2 - 10.5, thickness + post_h - 1.0])
            cube([thickness + 1, 21, 5.5]);

        // 🔲 【右側面】MicroSDカード用窓（位置を基板エリアの中心に補正）
        translate([outer_w - thickness - 0.5, box_outer_d / 2 - 10.5, thickness + post_h - 1.0])
            cube([thickness + 1, 21, 5.5]);

        // 🔌 【手前側】端子用切り欠き（HDMI/USB用：1.1mm高）
        translate([thickness + clearance + 5, -0.5, (thickness + post_h + pi_h) - 2.0])
            cube([pi_w - 10, thickness + 1, box_h]);

        // 🧵 🛠️ 【アップデート】マジックバンド固定用の貫通スリット窓（左右対称に2箇所）
        // スリットサイズ: 幅(X) 16mm × 奥行き(Y) 2.5mm (10〜15mm幅のマジックバンドに対応)
        // 左側のスリット穴
        translate([thickness + 4, outer_d - thickness - 4.0, -0.5]) 
            cube([16, 2.5, thickness + 1]);
            
        // 右側のスリット穴
        translate([outer_w - thickness - 20, outer_d - thickness - 4.0, -0.5]) 
            cube([16, 2.5, thickness + 1]);
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
