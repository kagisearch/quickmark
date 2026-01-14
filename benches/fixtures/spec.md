# Markdown Test Output

Here's a comprehensive test of various markdown elements:

## Code Block Test

```rust
pub const KAGI_PLUGIN_NAMES: [&str; 23] = [
    "nl2br",
    "newline",
    "escape",
    "backticks",
    "emphasis",
    "kagi_image",
    "kagi_link",
    "kagi_contact_info",
    "inkjet",
    "entity",
    "code",
    "fence",
    "blockquote",
    "hr",
    "list",
    "reference",
    "heading",
    "lheading",
    "paragraph",
    "citation",
    "table",
    "inline_math",
    "display_math",
];
```

## Text Formatting Tests

- **Bold text** for emphasis
- *Italic text* for subtle emphasis
- ```inline code``` for technical terms
- Regular text for normal content

## List Tests

### Unordered List
- First item
- Second item
    - Nested item A
    - Nested item B
        - Deeply nested item
- Third item

### Ordered List
1. First step
2. Second step
    1. Sub-step A
    2. Sub-step B
3. Third step

## Mathematical Expression Tests

### Inline Math
The quadratic formula is $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.

### Display Math
$$\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}$$

### Matrix Example
$$A = \begin{bmatrix} 1 & 2 & 3 \\ 4 & 5 & 6 \\ 7 & 8 & 9 \end{bmatrix}$$

## Table Test

| Plugin Name | Category | Description |
|-------------|----------|-------------|
| ```nl2br``` | Text | Newline to break conversion |
| ```emphasis``` | Formatting | Bold and italic text |
| ```code``` | Technical | Code block rendering |
| ```table``` | Structure | Table formatting |

## Blockquote Test

> This is a blockquote that demonstrates how quoted text appears in markdown. It can span multiple lines and is useful for highlighting important information or citations.

## Link Test

Here's a link to [Kagi Search](https://kagi.com) for reference.

## Horizontal Rule Test

---

## Special Characters and Escaping

Unicode subscripts: H₂O, CO₂
Unicode superscripts: E = mc²
Dollar amounts: I have $5 in my wallet
Special symbols: © ® ™ § ¶

## Image

![Image 1](www.example.com)

![Image 2](www.example.com)

## Contact Info

416-000-0000

rehan@kagi.com

This test covers the major markdown elements that would be processed by the plugins listed in your Rust array.
