const {
  runPythonScraper,
} = require("../services/pythonScraperService");

function getFirstValue(singleValue, arrayValue) {
  if (
    typeof singleValue === "string" &&
    singleValue.trim() !== ""
  ) {
    return singleValue.trim();
  }

  if (Array.isArray(arrayValue) && arrayValue.length > 0) {
    const firstValue = arrayValue.find(
      (value) =>
        typeof value === "string" &&
        value.trim() !== ""
    );

    return firstValue ? firstValue.trim() : null;
  }

  return null;
}

async function startScraping(request, response) {
  const { url } = request.body;

  if (typeof url !== "string" || url.trim() === "") {
    return response.status(400).json({
      success: false,
      message: "URL is required",
    });
  }

  let normalizedUrl;

  try {
    const parsedUrl = new URL(url.trim());

    if (
      parsedUrl.protocol !== "http:" &&
      parsedUrl.protocol !== "https:"
    ) {
      return response.status(400).json({
        success: false,
        message: "Only HTTP and HTTPS URLs are allowed",
      });
    }

    normalizedUrl = parsedUrl.toString();
  } catch (error) {
    return response.status(400).json({
      success: false,
      message: "Invalid URL",
    });
  }

  try {
    const scrapedData = await runPythonScraper(
      normalizedUrl
    );

    if (
      !scrapedData ||
      typeof scrapedData !== "object"
    ) {
      throw new Error(
        "Python scraper returned invalid data"
      );
    }

    if (
      scrapedData.success === false ||
      scrapedData.error
    ) {
      throw new Error(
        scrapedData.error ||
        "Python scraper could not scrape the website"
      );
    }

    const phone = getFirstValue(
      scrapedData.phone,
      scrapedData.phones
    );

    const email = getFirstValue(
      scrapedData.email,
      scrapedData.emails
    );

    const phones = Array.isArray(scrapedData.phones)
      ? scrapedData.phones
      : phone
        ? [phone]
        : [];

    const emails = Array.isArray(scrapedData.emails)
      ? scrapedData.emails
      : email
        ? [email]
        : [];

    /*
     * مهم:
     * هنا فقط نرجع البيانات إلى الـFrontend.
     * لا يوجد أي INSERT أو UPDATE بقاعدة البيانات.
     */
    return response.status(200).json({
      success: true,
      message: "Scraping completed successfully",

      data: {
        name: scrapedData.name || "",
        title: scrapedData.title || "",
        description: scrapedData.description || "",
        address: scrapedData.address || "",
        url: scrapedData.url || normalizedUrl,
        og_image: scrapedData.og_image || "",

        keywords: Array.isArray(scrapedData.keywords)
          ? scrapedData.keywords
          : [],

        favicon: scrapedData.favicon || "",

        social_links: Array.isArray(
          scrapedData.social_links
        )
          ? scrapedData.social_links
          : [],

        phone: phone || "",
        email: email || "",

        phones,
        emails,

        pages_scraped: Array.isArray(
          scrapedData.pages_scraped
        )
          ? scrapedData.pages_scraped
          : [],
      },
    });
  } catch (error) {
    console.error(
      "Scraping failed:",
      error.message
    );

    return response.status(500).json({
      success: false,
      message: "Scraping failed",
      error: error.message,
    });
  }
}

module.exports = {
  startScraping,
};