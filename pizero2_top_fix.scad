// ==========================================
// Raspberry Pi Zero 2 W - Bento Box (Top Cover) - Clean GPIO Slit (Y=2.0)
// ==========================================

// --- Raspberry Pi Zero 2 W 基本サイズ ---
pi_w = 69.0; // SDカードの2mmはみ出しを含めた調整値
pi_d = 30.0; 

// --- ケースの基本設定 ---
thickness       = 1.0;    // 周囲の壁の厚み (1.0mm)
clearance       = 1.0;    // 基板とケース内壁の隙間
cover_thickness = 3.0;    // 蓋の天面プレート自体の厚み (3.0mm)
cover_h         = 1.5;    // 内部部品と干渉しないようインロー高さを1.5mmに最適化

// 内寸と外寸の計算
inner_w = pi_w + (clearance * 2);
inner_d = pi_d + (clearance * 2);
outer_w = inner_w + (thickness * 2);
outer_d = inner_d + (thickness * 2); // 正確に 34.0mm に固定

// 🔩 反対側（奥側）のフチから手前に向かって「9.0mm」離した位置（Y=25.0）に固定
bracket_y = 25.0; 

bracket_screw_pass_r = 1.1; // M2ネジ用 (直径2.2mmの穴)

// 📌 GPIOリボンケーブル用スリット窓の寸法
gpio_w   = 62.0; // 窓の長さ (X軸方向)
gpio_d   = 6.5;  // 窓の幅 (Y軸方向)

// 🎤 マイク穴の設定
mic_dia = 12.3;
mic_r   = mic_dia / 2;
mic_x   = outer_w / 2.6;  // X軸の中央に配置
mic_y   = 19.5;         // GPIOスリット(Y=2.0~8.5)とネジ穴(Y=25.0)の間に配置

$fn = 64; // 円をより滑らかにするために32から64に変更

// --- メインレンダリング ---
translate([0, outer_d, cover_thickness])
    top_cover();

// --- モジュール定義 ---
module top_cover() {
    fit_gap       = 0.2; // 嵌め合い部（インロー）のクリアランス
    lip_thickness = 0.8; // インローの突起自体の肉厚
    
    difference() {
        union() {
            // 1. 蓋の天面プレート（厚み3.0mm）
            cube([outer_w, outer_d, cover_thickness]);
            
            // 2. 凹凸の噛み合わせ（インロー固定部）
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

        // 🔩 3mmの天面からインロー頂点までを完全に撃ち抜く貫通ネジ穴
        // X = 7.0mm と 16.0mm、Y = 25.0mm の正しいブラケットピッチ位置
        translate([0, 0, -0.5]) {
            bracket_mount_hole(7.0, bracket_y);
            bracket_mount_hole(16.0, bracket_y);
        }

        // 📌 GPIOスリット窓を手前フチ（Y=2.0）に配置
        translate([thickness + clearance + 3.5, 2.0, -0.5])
            cube([gpio_w, gpio_d, cover_thickness + cover_h + 1.0]);

        // 🎤 マイク用貫通穴
        translate([mic_x, mic_y, -0.5])
            cylinder(r = mic_r, h = cover_thickness + cover_h + 1.0);
    }
}

// ネジ穴と皿モミ加工モジュール
module bracket_mount_hole(x, y) {
    translate([x, y, 0]) {
        // M2ネジ用の全貫通穴
        cylinder(r = bracket_screw_pass_r, h = cover_thickness + cover_h + 2.0);
        
        // ネジ頭用の皿モミ（深さ1.2mm、直径3.6mm）
        translate([0, 0, -0.1])
            cylinder(r = 1.8, h = 1.3);
    }
}
