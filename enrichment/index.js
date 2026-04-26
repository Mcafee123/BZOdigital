import express from "express";
import { readFileSync } from "node:fs";

const app = express();
const port = Number(process.env.PORT || 3232);
const maxInputLength = 100_000;

const zhLaws = JSON.parse(
    readFileSync(new URL("./zh/src/zhlex_laws_summary.json", import.meta.url), "utf8")
);

const officialZhLawsByAbbreviation = new Map();

for (const law of zhLaws) {
    const abbreviation = normalizeLawAbbreviation(law.law_title_abbreviation_latest);

    if (!abbreviation || !law.in_force || !law.dynamic_prod_url) {
        continue;
    }

    officialZhLawsByAbbreviation.set(abbreviation, law);
}

// Regex for article and paragraph references in DE, FR and IT.
const citationMarkerPattern = String.raw`§+|Art|art|Artikel|article|Article|articolo|Articolo|Paragraph|Par|par`;
const provisionPattern = String.raw`\d+(?:[a-zA-Z]\b)?`;
const citationDetailPattern =
    String.raw`(?:\s*(?:Abs|Absatz|Al|al|Cpv|cpv)\.?\s*${provisionPattern})?` +
    String.raw`(?:\s*(?:Ziff|Ziffer|Ch|ch|N|n)\.?\s*${provisionPattern})?` +
    String.raw`(?:\s*(?:Lit|lit|Buchstabe|Bchst|Let|let|Lett|lett)\.?\s*[A-Za-z])?`;
const lawAbbreviationToken = String.raw`(?:[\p{Lu}\p{N}][\p{L}\p{N}/-]*|[\p{Ll}]+(?:[\p{Lu}\p{N}/-])[\p{L}\p{N}/-]*)`;
const combinationConnectorPattern = String.raw`(?:,|;|\b(?:und|sowie|oder|respektive|et|ou|ainsi\s+que|soit|e|ed|o|oppure|nonché|nonche)\b|\bbzw\.?)`;
const combinationSeparatorPattern = String.raw`\s*${combinationConnectorPattern}\s*`;
const regexCombinedLawReference = new RegExp(
    String.raw`(?<![\p{L}\p{N}_])` +
    String.raw`(?<firstCitation>(?<marker>${citationMarkerPattern})\.?\s*(?<firstProvision>${provisionPattern})${citationDetailPattern})` +
    String.raw`(?<tail>(?:${combinationSeparatorPattern}${provisionPattern})+)` +
    String.raw`\s+(?<law>${lawAbbreviationToken}(?:\s+${lawAbbreviationToken}){0,3})(?![\p{L}\p{N}_])`,
    "gu"
);
const regexCombinedDefaultLawReference = new RegExp(
    String.raw`(?<![\p{L}\p{N}_])` +
    String.raw`(?<firstCitation>(?<marker>${citationMarkerPattern})\.?\s*(?<firstProvision>${provisionPattern})${citationDetailPattern})` +
    String.raw`(?<tail>(?:${combinationSeparatorPattern}${provisionPattern})+)(?!\s+${lawAbbreviationToken})(?![\p{L}\p{N}_])`,
    "gu"
);
const regexLawReference = new RegExp(
    String.raw`(?<![\p{L}\p{N}_])(?<marker>${citationMarkerPattern})\.?\s*` +
    String.raw`(?<provision>${provisionPattern})` +
    String.raw`(?:\s*(?<paragraphLabel>Abs|Absatz|Al|al|Cpv|cpv)\.?\s*(?<paragraph>${provisionPattern}))?` +
    String.raw`(?:\s*(?<numberLabel>Ziff|Ziffer|Ch|ch|N|n)\.?\s*(?<number>${provisionPattern}))?` +
    String.raw`(?:\s*(?<letterLabel>Lit|lit|Buchstabe|Bchst|Let|let|Lett|lett)\.?\s*(?<letter>[A-Za-z]))?` +
    String.raw`(?:\s+(?<law>${lawAbbreviationToken}(?:\s+${lawAbbreviationToken}){0,3})(?![\p{L}\p{N}_]))?`,
    "gu"
);

//Regex for BGE/ATF/DTF (DE/FR/IT)
const regexBGE = /(?:(?:(BGE|ATF|DTF)\.?\s*)?(\d+(?:\w\b)?)\s*M{0,4}(IV|V|I{1,3}[ab]?)+\s*(\d+(?:\w\b)?))/gi

//Regex for BGer reference Number (Geschäftsnr./Num. référence/N. riferimento)
const regexBGer = /(\d+)([A-Z])_(\d+\/\d+)/g

function enrichMarkdown(text, options = {}) {
    const protectedMarkdown = [];

    text = protectCombinedLawReferences(text, protectedMarkdown, options.defaultLaw);

    // Match all article/paragraph references, then only link official Canton Zurich abbreviations.
    text = text.replace(regexLawReference, function (ref, ...args) {
        const groups = args.at(-1);
        const law = getLawForReference(groups.law, options.defaultLaw);

        if (!law) {
            return ref;
        }

        return buildMarkdownLink(ref, buildOdatProvisionUrl(law, groups.provision));
    });

    // Highlight reference Numbers
    text = text.replace(regexBGer, function (ref) {
        // let response = [...ref.matchAll(regexBGer)]; //if array of matches needed
        return buildMarkdownLink(ref, "https://links.weblaw.ch/" + encodeURIComponent(ref)); //Todo convert link to admin.ch link
    });

    //Highlight BGEs with <a>...</a>
    return text.replace(regexBGE, function (ref) {
        let res = [...ref.matchAll(regexBGE)];
        let lang;

        if (!res[0][1]) {
            res[0][1] = "BGE";
        }
        if (res[0][1] == "BGE") {
            lang = "de";
        }
        if (res[0][1] == "ATF") {
            lang = "fr";
        }
        if (res[0][1] == "DTF") {
            lang = "it";
        }
        let link = "https://www.bger.ch/ext/eurospider/live/" + lang + "/php/aza/http/index.php?lang=" + lang + "&type=show_document&page=1&from_date=&to_date=&sort=relevance&insertion_date=&top_subcollection_aza=all&query_words=&rank=0&azaclir=aza&highlight_docid=atf%3A%2F%2F" + res[0][2] + "-" + res[0][3] + "-" + res[0][4] + "%3A" + lang + "&number_of_ranks=0#page" + res[0][4];
        return buildMarkdownLink(ref, link);
    }).replace(/\uE000(\d+)\uE001/g, function (placeholder, index) {
        return protectedMarkdown[Number(index)] || placeholder;
    })
};

function protectCombinedLawReferences(text, protectedMarkdown, defaultLaw) {
    text = text.replace(regexCombinedLawReference, function (ref, ...args) {
        const groups = args.at(-1);
        const law = officialZhLawsByAbbreviation.get(normalizeLawAbbreviation(groups.law));

        if (!law) {
            return protectMarkdown(ref, protectedMarkdown);
        }

        const linkedReference = buildCombinedLawReferenceMarkdown(groups, law);
        return protectMarkdown(linkedReference, protectedMarkdown);
    });

    if (!defaultLaw) {
        return text;
    }

    return text.replace(regexCombinedDefaultLawReference, function (ref, ...args) {
        const groups = args.at(-1);
        const linkedReference = buildCombinedLawReferenceMarkdown(groups, defaultLaw);
        return protectMarkdown(linkedReference, protectedMarkdown);
    });
}

function buildCombinedLawReferenceMarkdown(groups, law) {
    const linkedFirstCitation = buildMarkdownLink(
        groups.firstCitation,
        buildOdatProvisionUrl(law, groups.firstProvision)
    );

    const linkedTail = groups.tail.replace(
        new RegExp(String.raw`(${combinationSeparatorPattern})(?<provision>${provisionPattern})`, "gu"),
        function (ref, separator, ...args) {
            const tailGroups = args.at(-1);
            return separator + buildMarkdownLink(
                tailGroups.provision,
                buildOdatProvisionUrl(law, tailGroups.provision)
            );
        }
    );

    return linkedFirstCitation + linkedTail + (groups.law ? " " + groups.law : "");
}

function protectMarkdown(markdown, protectedMarkdown) {
    const index = protectedMarkdown.push(markdown) - 1;
    return "\uE000" + index + "\uE001";
}

function getLawForReference(referenceLawAbbreviation, defaultLaw) {
    if (referenceLawAbbreviation) {
        return officialZhLawsByAbbreviation.get(normalizeLawAbbreviation(referenceLawAbbreviation));
    }

    return defaultLaw || null;
}

function buildOdatProvisionUrl(law, provision) {
    return law.dynamic_prod_url + "-latest.html#seq-0-prov-" + encodeURIComponent(provision.toLowerCase());
}

function normalizeLawAbbreviation(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
}

function buildMarkdownLink(label, url) {
    return "[" + escapeMarkdownLinkLabel(label) + "](" + encodeMarkdownLinkDestination(url) + ")";
}

function escapeMarkdownLinkLabel(value) {
    return String(value).replace(/([\\\[\]])/g, "\\$1");
}

function encodeMarkdownLinkDestination(value) {
    return String(value)
        .replaceAll(" ", "%20")
        .replaceAll("(", "%28")
        .replaceAll(")", "%29");
}

app.disable("x-powered-by");
app.use(express.json({ limit: "128kb" }));

app.get("/health", (request, response) => {
    response.json({ status: "ok" });
});

app.post("/enrich", (request, response) => {
    const { text } = request.body || {};
    const defaultLawInput = request.body?.["default-law"];

    if (typeof text !== "string") {
        response.status(400).json({ error: "Request body must include a string field named text." });
        return;
    }

    if (text.length > maxInputLength) {
        response.status(413).json({ error: "Text exceeds the maximum allowed length." });
        return;
    }

    if (defaultLawInput !== undefined && typeof defaultLawInput !== "string") {
        response.status(400).json({ error: "Optional default-law field must be a string." });
        return;
    }

    const defaultLaw = defaultLawInput
        ? officialZhLawsByAbbreviation.get(normalizeLawAbbreviation(defaultLawInput))
        : null;

    if (defaultLawInput && !defaultLaw) {
        response.status(400).json({ error: "default-law must match an official Canton Zurich law abbreviation." });
        return;
    }

    response.json({ markdown: enrichMarkdown(text, { defaultLaw }) });
});

app.listen(port, "0.0.0.0", () => {
    console.log(`enrichment dev server listening on ${port}`);
});
