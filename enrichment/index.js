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
const lawAbbreviationToken = String.raw`(?:[\p{Lu}\p{N}][\p{L}\p{N}/-]*|[\p{Ll}]+[\p{Lu}][\p{L}\p{N}/-]*)`;
const regexLawReference = new RegExp(
    String.raw`(?<![\p{L}\p{N}_])(?<marker>§+|Art|art|Artikel|article|Article|articolo|Articolo|Paragraph|Par|par)\.?\s*` +
    String.raw`(?<provision>\d+[a-zA-Z]?)` +
    String.raw`(?:\s*(?<paragraphLabel>Abs|Absatz|Al|al|Cpv|cpv)\.?\s*(?<paragraph>\d+[a-zA-Z]?))?` +
    String.raw`(?:\s*(?<numberLabel>Ziff|Ziffer|Ch|ch|N|n)\.?\s*(?<number>\d+[a-zA-Z]?))?` +
    String.raw`(?:\s*(?<letterLabel>Lit|lit|Buchstabe|Bchst|Let|let|Lett|lett)\.?\s*(?<letter>[A-Za-z]))?` +
    String.raw`\s+(?<law>${lawAbbreviationToken}(?:\s+${lawAbbreviationToken}){0,3})(?![\p{L}\p{N}_])`,
    "gu"
);

//Regex for BGE/ATF/DTF (DE/FR/IT)
const regexBGE = /(?:(?:(BGE|ATF|DTF)\.?\s*)?(\d+(?:\w\b)?)\s*M{0,4}(IV|V|I{1,3}[ab]?)+\s*(\d+(?:\w\b)?))/gi

//Regex for BGer reference Number (Geschäftsnr./Num. référence/N. riferimento)
const regexBGer = /(\d+)([A-Z])_(\d+\/\d+)/g

function enrichMarkdown(text) {
    // Match all article/paragraph references, then only link official Canton Zurich abbreviations.
    text = text.replace(regexLawReference, function (ref, ...args) {
        const groups = args.at(-1);
        const law = officialZhLawsByAbbreviation.get(normalizeLawAbbreviation(groups.law));

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
    })
};

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

    if (typeof text !== "string") {
        response.status(400).json({ error: "Request body must include a string field named text." });
        return;
    }

    if (text.length > maxInputLength) {
        response.status(413).json({ error: "Text exceeds the maximum allowed length." });
        return;
    }

    response.json({ markdown: enrichMarkdown(text) });
});

app.listen(port, "0.0.0.0", () => {
    console.log(`enrichment dev server listening on ${port}`);
});
