/* Small D3 v7 helpers for the impact-tracker dashboard: a metric line chart
 * and a group activity timeline. Both are read from plain JS objects the
 * templates embed as inline <script type="application/json"> data, so this
 * file has no build step of its own. */
(function () {
  "use strict";

  const SERIES_VARS = [
    "--series-1", "--series-2", "--series-3", "--series-4",
    "--series-5", "--series-6", "--series-7", "--series-8",
  ];

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function seriesColor(index) {
    return cssVar(SERIES_VARS[index % SERIES_VARS.length]);
  }

  function ensureTooltip() {
    let tip = document.querySelector(".viz-tooltip");
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "tooltip viz-tooltip";
      document.body.appendChild(tip);
    }
    return tip;
  }

  function showTooltip(tip, html, x, y) {
    tip.innerHTML = html;
    tip.style.left = `${x + 14}px`;
    tip.style.top = `${y + 14}px`;
    tip.style.opacity = "1";
  }

  function hideTooltip(tip) {
    tip.style.opacity = "0";
  }

  /**
   * Draw a small-multiple line chart for one or more metric series on a
   * shared time axis.
   *
   * @param {string} selector - container element selector
   * @param {Array<{id: string, label: string, points: Array<{date: string, value: number}>}>} series
   */
  function drawLineChart(selector, series) {
    const container = document.querySelector(selector);
    if (!container || !series.length) return;

    const width = container.clientWidth || 480;
    const height = 220;
    const margin = { top: 10, right: 16, bottom: 24, left: 40 };

    const allPoints = series.flatMap((s) => s.points);
    const x = d3
      .scaleUtc()
      .domain(d3.extent(allPoints, (d) => new Date(d.date)))
      .range([margin.left, width - margin.right]);
    const y = d3
      .scaleLinear()
      .domain([0, d3.max(allPoints, (d) => d.value) * 1.1 || 1])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const svg = d3
      .select(container)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", "100%")
      .attr("height", height);

    svg
      .append("g")
      .attr("class", "gridline")
      .selectAll("line")
      .data(y.ticks(4))
      .join("line")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", (d) => y(d))
      .attr("y2", (d) => y(d));

    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).ticks(Math.min(6, allPoints.length)).tickSizeOuter(0));

    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0));

    const line = d3
      .line()
      .curve(d3.curveMonotoneX)
      .x((d) => x(new Date(d.date)))
      .y((d) => y(d.value));

    series.forEach((s, i) => {
      const color = seriesColor(i);
      svg
        .append("path")
        .datum(s.points)
        .attr("fill", "none")
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .attr("stroke-linecap", "round")
        .attr("d", line);
    });

    if (series.length > 1) {
      const legend = d3.select(container).append("div").attr("class", "legend");
      series.forEach((s, i) => {
        const item = legend.append("span");
        item.append("span").attr("class", "swatch").style("background", seriesColor(i));
        item.append("span").text(s.label);
      });
    }

    // Hover crosshair + tooltip, shared across series.
    const tip = ensureTooltip();
    const focusLine = svg
      .append("line")
      .attr("class", "gridline")
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("opacity", 0);
    const focusDots = series.map((_, i) =>
      svg
        .append("circle")
        .attr("r", 4)
        .attr("fill", seriesColor(i))
        .attr("stroke", "var(--surface-1)")
        .attr("stroke-width", 1.5)
        .attr("opacity", 0)
    );

    const bisect = d3.bisector((d) => new Date(d.date)).left;

    svg
      .append("rect")
      .attr("x", margin.left)
      .attr("y", margin.top)
      .attr("width", Math.max(0, width - margin.left - margin.right))
      .attr("height", Math.max(0, height - margin.top - margin.bottom))
      .attr("fill", "transparent")
      .on("mousemove", function (event) {
        const [mx] = d3.pointer(event);
        const date = x.invert(mx);
        const rows = series.map((s, i) => {
          const idx = bisect(s.points, date);
          const point = s.points[Math.min(idx, s.points.length - 1)] || s.points[0];
          return { label: s.label, point };
        });
        if (!rows.length || !rows[0].point) return;
        const refDate = rows[0].point.date;
        focusLine.attr("x1", x(new Date(refDate))).attr("x2", x(new Date(refDate))).attr("opacity", 1);
        rows.forEach((r, i) => {
          focusDots[i]
            .attr("cx", x(new Date(r.point.date)))
            .attr("cy", y(r.point.value))
            .attr("opacity", 1);
        });
        const html =
          `<strong>${refDate}</strong><br>` +
          rows.map((r) => `${r.label}: ${r.point.value}`).join("<br>");
        showTooltip(tip, html, event.pageX, event.pageY);
      })
      .on("mouseleave", function () {
        focusLine.attr("opacity", 0);
        focusDots.forEach((d) => d.attr("opacity", 0));
        hideTooltip(tip);
      });
  }

  /**
   * Draw a group activity timeline: one lane per output, dots for each event.
   *
   * @param {string} selector
   * @param {Array<{id: string, label: string, events: Array<{date: string, kind: string, label: string, url: string}>}>} lanes
   */
  function drawTimeline(selector, lanes) {
    const container = document.querySelector(selector);
    if (!container) return;
    const withEvents = lanes.filter((l) => l.events && l.events.length);
    if (!withEvents.length) {
      container.innerHTML = '<p class="lede">No dated events recorded yet.</p>';
      return;
    }

    const width = container.clientWidth || 800;
    const rowHeight = 34;
    const margin = { top: 10, right: 16, bottom: 28, left: 160 };
    const height = margin.top + margin.bottom + withEvents.length * rowHeight;

    const allDates = withEvents.flatMap((l) => l.events.map((e) => new Date(e.date)));
    const x = d3
      .scaleUtc()
      .domain(d3.extent(allDates))
      .nice()
      .range([margin.left, width - margin.right]);

    const svg = d3
      .select(container)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", "100%")
      .attr("height", height);

    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).ticks(Math.min(8, allDates.length)).tickSizeOuter(0));

    const tip = ensureTooltip();

    withEvents.forEach((lane, i) => {
      const rowY = margin.top + i * rowHeight + rowHeight / 2;
      const color = seriesColor(i);

      svg
        .append("line")
        .attr("class", "gridline")
        .attr("x1", margin.left)
        .attr("x2", width - margin.right)
        .attr("y1", rowY)
        .attr("y2", rowY);

      svg
        .append("text")
        .attr("x", margin.left - 12)
        .attr("y", rowY)
        .attr("text-anchor", "end")
        .attr("dominant-baseline", "middle")
        .attr("fill", "var(--text-secondary)")
        .attr("font-size", 12)
        .text(lane.label);

      svg
        .selectAll(`.dot-${i}`)
        .data(lane.events)
        .join("circle")
        .attr("class", `dot-${i}`)
        .attr("cx", (d) => x(new Date(d.date)))
        .attr("cy", rowY)
        .attr("r", 5)
        .attr("fill", color)
        .attr("stroke", "var(--surface-1)")
        .attr("stroke-width", 1.5)
        .style("cursor", (d) => (d.url ? "pointer" : "default"))
        .on("mousemove", function (event, d) {
          showTooltip(tip, `<strong>${lane.label}</strong><br>${d.label} &middot; ${d.date}`, event.pageX, event.pageY);
        })
        .on("mouseleave", () => hideTooltip(tip))
        .on("click", (_, d) => {
          if (d.url) window.open(d.url, "_blank", "noopener");
        });
    });
  }

  window.ImpactCharts = { drawLineChart, drawTimeline };
})();
