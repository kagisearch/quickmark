use std::fs;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use quickmark::{plugins::kagi_plugins::KAGI_PLUGIN_NAMES, MDParser};
use std::hint::black_box;

fn render_with(input: &str, plugins: &[&str]) {
    let mut parser = MDParser::new("zero").unwrap();
    for &p in plugins {
        parser._enable_str(p).unwrap();
    }
    let _html = parser.render(input, true).unwrap();
}

fn bench_kagi_plugins(c: &mut Criterion) {
    let input = fs::read_to_string("benches/fixtures/spec.md").expect("fixture not found");
    let input = input.repeat(4);

    c.bench_function("baseline", |b| {
        b.iter(|| render_with(black_box(&input), black_box(&[][..])))
    });

    for idx in 0..KAGI_PLUGIN_NAMES.len() {
        let enabled = &[KAGI_PLUGIN_NAMES[idx]];
        let id = BenchmarkId::new("kagi_single", KAGI_PLUGIN_NAMES[idx]);

        c.bench_with_input(id, &enabled, |b, enabled| {
            b.iter(|| render_with(black_box(&input), black_box(*enabled)))
        });
    }
}

criterion_group!(benches, bench_kagi_plugins);
criterion_main!(benches);
