const express = require("express");
const { execFile } = require("node:child_process");
const path = require("node:path");
const cors = require('cors');
const app = express();
app.use(cors());

function runPythonScraper(targetUrl) {
    return new Promise((resolve, reject) => {
        const scriptPath = path.join(
            __dirname,
            "../../python/scraper.py"
        );

        execFile(
            "python",
            [scriptPath, targetUrl],
            {
                windowsHide: true,
                maxBuffer: 1024 * 1024
            },
            (error, stdout, stderr) => {
                if (error) {
                    return reject(
                        new Error(stderr.trim() || error.message)
                    );
                }

                try {
                    const scrapedData = JSON.parse(stdout.trim());

                    if (scrapedData.error) {
                        return reject(
                            new Error(scrapedData.error)
                        );
                    }

                    resolve(scrapedData);
                } catch {
                    reject(
                        new Error(
                            "Python returned invalid JSON" + stdout
                        )
                    );
                }
            }
        );
    });
}

module.exports = {
    runPythonScraper
};