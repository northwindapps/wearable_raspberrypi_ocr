// ==========================================
// Raspberry Pi Zero 2 W - Bento Box (Top Cover) - Final Fixed Ver.
// ==========================================

// --- Raspberry Pi Zero 2 W 基本サイズ ---
pi_w = 69.0; // SDカードの2mmはみ出しを含めた調整値
pi_d = 30.0; 

// --- ケースの基本設定 ---
thickness = 1.0;    // テスト用の壁の厚み (1.0mm)
clearance = 1.0;    // 基板とケース内壁の隙間
cover_h   = 1.5;    // 【修正】内部部品と干渉しないようインロー高さを1.5mmに最適化

// 内寸と外寸の計算
inner_w = pi_w + (clearance * 2);
inner_d = pi_d + (clearance * 2);
outer_w = inner_w + (thickness * 2);
outer_d = inner_d + (thickness * 2);

// --- メインレンダリング ---
// 【修正】180度反転させたときにベッド（床）の上に正しく接地するように座標修正
translate([0, outer_d, thickness])
    rotate([180, 0, 0])
        top_cover();

// --- モジュール定義 ---
module top_cover() {
    fit_gap       = 0.2; // 嵌め合い部（インロー）のクリアランス
    lip_thickness = 0.8; // インローの突起自体の肉厚
    
    difference() {
        union() {
            // 蓋の天面プレート
            cube([outer_w, outer_d, thickness]);
            
            // 凹凸の噛み合わせ（インロー固定部）
            translate([thickness + fit_gap, thickness + fit_gap, thickness])
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
        
        // ✂️ 【重要追加】ボトム側の左右21mm窓と干渉するインローの壁をカットする処理
        // 左側のインローを逃がす（21mm窓に連動）
        translate([thickness, outer_d/2 - 11.5, thickness - 0.5])
            cube([lip_thickness + 1, 23, cover_h + 1]);
            
        // 右側のインローを逃がす（21mm窓に連動）
        translate([outer_w - thickness - lip_thickness - 1, outer_d/2 - 11.5, thickness - 0.5])
            cube([lip_thickness + 2, 23, cover_h + 1]);

        // 放熱用のスリット穴
        for (i = [0 : 5]) {
            translate([outer_w / 2 - 15 + (i * 5), outer_d / 2 - 10, -0.5])
                cube([2, 20, thickness + 1]);
        }
    }
}
