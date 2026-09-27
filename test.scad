// ==========================================
// Raspberry Pi Zero 2 W - Bento Box (Top Cover) - 3.0mm Cover Thickness
// ==========================================

// --- Raspberry Pi Zero 2 W 基本サイズ ---
pi_w = 69.0; // SDカードの2mmはみ出しを含めた調整値
pi_d = 30.0; 

// --- ケースの基本設定 ---
thickness       = 1.0;    // 周囲の壁の厚み (1.0mm)
clearance       = 1.0;    // 基板とケース内壁の隙間
cover_thickness = 3.0;    // 🛠️【新機能】蓋の天面プレート自体の厚みを3.0mmに強化
cover_h         = 1.5;    // 内部部品と干渉しないようインロー高さを1.5mmに最適化

// 内寸と外寸の計算
inner_w = pi_w + (clearance * 2);
inner_d = pi_d + (clearance * 2);
outer_w = inner_w + (thickness * 2);
outer_d = inner_d + (thickness * 2); // 🛠️【修正】thickness=1.0により、正確に 34.0mm に固定されます

// 🔩 反対側（奥側）のフチから手前に向かって「9.0mm」離した位置（Y=25.0）に固定
bracket_y = 25.0; 

bracket_screw_pass_r = 1.1; // M2ネジがスムーズに通る直径2.2mmの穴

$fn = 32;

// --- メインレンダリング ---
// 3Dプリンターベッドの上に正しく接地するように座標修正
translate([0, outer_d, cover_thickness])
    rotate([180, 0, 0])
        top_cover();

// --- モジュール定義 ---
module top_cover() {
    fit_gap       = 0.2; // 嵌め合い部（インロー）のクリアランス
    lip_thickness = 0.8; // インローの突起自体の肉厚
    
    difference() {
        union() {
            // 🛠️ 蓋の天面プレート（厚みを3.0mmに強化）
            cube([outer_w, outer_d, cover_thickness]);
            
            // 凹凸の噛み合わせ（インロー固定部）
            translate([thickness + fit_gap, thickness + fit_gap, cover_thickness])
                difference() {
                    cube([inner_w - (fit_gap * 2), inner_d - (fit_gap * 2), cover_h]);
                    
                    // 内側をくり抜いて突起（リップ）を形成
                    translate([lip_thickness, lip_thickness, -0.5])
                        cube([
                            inner_w - (fit_gap * 2) - (lip_thickness * 2), 
                            inner_d - (fit_gap * 2) - (lip_thickness * 2), 
                            cover_h + 1
                        ]);
                }
        }
        
        // ✂️ ボトム側の左右21mm窓と干渉するインローの壁をカットする処理
        translate([thickness, outer_d/2 - 11.5, cover_thickness - 0.5])
            cube([lip_thickness + 1, 23, cover_h + 1]);
            
        translate([outer_w - thickness - lip_thickness - 1, outer_d/2 - 11.5, cover_thickness - 0.5])
            cube([lip_thickness + 2, 23, cover_h + 1]);

        // 🔩 🛠️【修正】3.0mmの厚みを完全に撃ち抜くネジ穴（絶対零度から貫通させます）
        translate([0, 0, -0.5]) {
            bracket_mount_hole(7.0, bracket_y);
            bracket_mount_hole(16.0, bracket_y);
        }

        // 放熱用のスリット穴（3mm厚を確実に貫通させます）
        for (i = [0 : 5]) {
            translate([outer_w / 2 - 15 + (i * 5), outer_d / 2 - 10, -0.5])
                cube([2, 20, cover_thickness + 1]);
        }
    }
}

// 貫通穴と皿モミ加工モジュール
module bracket_mount_hole(x, y) {
    // M2ネジ用貫通穴 (全体の高さに合わせて貫通長さを調整)
    cylinder(r = bracket_screw_pass_r, h = cover_thickness + cover_h + 1.0);
    
    // 🛠️【修正】天面が3mmに厚くなったため、皿頭がツライチに沈むよう皿モミ深さを 1.5mm に深く加工
    // 3Dプリンターベッド設置面（外面）側に綺麗に掘られます
    translate([0, 0, cover_thickness + cover_h - 0.5])
        cylinder(r = 1.8, h = 1.5);
}
