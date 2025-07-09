; ModuleID = "quick-helpies"
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"

define i32 @p2_floor(i32 %a, i32 %b) {
entry:
  %div = sdiv i32 %a, %b
  %rem = srem i32 %a, %b
  %cond = icmp ne i32 %rem, 0

  %xor_ab = xor i32 %a, %b
  %sign_mismatch = icmp slt i32 %xor_ab, 0

  %need_floor = and i1 %cond, %sign_mismatch

  %div_minus_1 = sub i32 %div, 1
  %floor_div = select i1 %need_floor, i32 %div_minus_1, i32 %div

  ret i32 %floor_div
}

define i32 @p2_mod(i32 %a, i32 %b) {
entry:
  %floor_div = call i32 @p2_floor(i32 %a, i32 %b)
  %mul = mul i32 %b, %floor_div
  %mod = sub i32 %a, %mul
  ret i32 %mod
}