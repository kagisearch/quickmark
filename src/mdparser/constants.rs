use phf::phf_map;
pub const MAIL_PREFIX: &str = "mailto:";
pub const PHONE_PREFIX: &str = "tel:";

// NOTE(Rehan): list of inkjet classes: https://docs.rs/inkjet/latest/src/inkjet/constants.rs.html#100-189
// list of standard pygments classes: https://pygments-doc.readthedocs.io/en/latest/_modules/pygments/token.html
pub static INKJET_TO_PYGMENTS_CLASS_MAP: phf::Map<&'static str, &'static str> = phf_map! {
    "attribute" => "na",
    "type" => "kt",
    "type builtin" => "kt",
    "type enum" => "nc",
    "type enum variant" => "no",
    "constructor" => "nf",

    "constant" => "no",
    "constant builtin" => "kc",
    "constant builtin boolean" => "kc",
    "constant character" => "sc",
    "constant character escape" => "se",
    "constant numeric" => "m",
    "constant numeric integer" => "mi",
    "constant numeric float" => "mf",

    "string" => "s",
    "string regexp" => "sr",
    "string special" => "ss",
    "string special path" => "sx",
    "string special url" => "sx",
    "string special symbol" => "ss",
    "escape" => "se",

    "comment" => "c",
    "comment line" => "c1",
    "comment block" => "cm",
    "comment block documentation" => "cs",

    "variable" => "n",
    "variable builtin" => "nb",
    "variable parameter" => "n",
    "variable other" => "nx",
    "variable other member" => "na",
    "label" => "nl",

    "punctuation" => "p",
    "punctuation delimiter" => "p",
    "punctuation bracket" => "p",
    "punctuation special" => "p",

    "operator" => "o",
    "keyword operator" => "ow",

    "keyword" => "k",
    "keyword control" => "kr",
    "keyword control conditional" => "kr",
    "keyword control repeat" => "kr",
    "keyword control import" => "kn",
    "keyword control return" => "kr",
    "keyword control exception" => "kr",
    "keyword directive" => "cp",
    "keyword function" => "kd",
    "keyword storage" => "kd",
    "keyword storage type" => "kt",
    "keyword storage modifier" => "kp",

    "function" => "nf",
    "function builtin" => "nb",
    "function method" => "nf",
    "function macro" => "fm", // 'fm' doesn't seem to be a standard pygments token but seems it emits for macro in pygments
    "function special" => "nf",

    "tag" => "nt",
    "tag builtin" => "nb",
    "namespace" => "nn",

    "special" => "bp",

    "markup" => "g",
    "markup heading" => "gh",
    "markup heading marker" => "gu",
    "markup heading 1" => "gh",
    "markup heading 2" => "gh",
    "markup heading 3" => "gh",
    "markup heading 4" => "gh",
    "markup heading 5" => "gh",
    "markup heading 6" => "gh",

    "markup list" => "g",
    "markup list unnumbered" => "g",
    "markup list numbered" => "g",
    "markup list checked" => "g",
    "markup list unchecked" => "g",

    "markup bold" => "gs",
    "markup italic" => "ge",
    "markup strikethrough" => "gd",

    "markup link" => "nl",
    "markup link url" => "nl",
    "markup link label" => "nl",
    "markup link text" => "nl",

    "markup quote" => "gu",
    "markup raw" => "go",
    "markup raw inline" => "go",
    "markup raw block" => "go",

    "diff" => "g",
    "diff plus" => "gi",
    "diff minus" => "gd",
    "diff delta" => "gu",
    "diff delta moved" => "gu",
};
