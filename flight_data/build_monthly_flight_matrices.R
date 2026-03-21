input_path <- file.path("flight_data", "state_flight_freq_final.csv")
output_dir <- "flight_data"
output_path <- file.path(output_dir, "state_flight_freq_norm_matrices.rds")

flight_freq <- read.csv(input_path, stringsAsFactors = FALSE)

state_levels <- sort(unique(c(
  flight_freq$ORIGIN_STATE_ABR,
  flight_freq$DEST_STATE_ABR
)))

year_month <- unique(flight_freq[c("YEAR", "MONTH")])
year_month <- year_month[order(year_month$YEAR, year_month$MONTH), ]

monthly_matrices <- list()

for (i in seq_len(nrow(year_month))) {
  year_value <- year_month$YEAR[i]
  month_value <- year_month$MONTH[i]

  monthly_data <- flight_freq[
    flight_freq$YEAR == year_value & flight_freq$MONTH == month_value,
  ]

  max_departures <- max(monthly_data$DEPARTURES_PERFORMED, na.rm = TRUE)
  monthly_data$DEPARTURES_NORMALIZED <- if (is.finite(max_departures) && max_departures > 0) {
    monthly_data$DEPARTURES_PERFORMED / max_departures
  } else {
    0
  }

  monthly_matrix <- xtabs(
    DEPARTURES_NORMALIZED ~
      factor(ORIGIN_STATE_ABR, levels = state_levels) +
      factor(DEST_STATE_ABR, levels = state_levels),
    data = monthly_data
  )

  monthly_matrix <- as.matrix(monthly_matrix)
  rownames(monthly_matrix) <- state_levels
  colnames(monthly_matrix) <- state_levels
  names(dimnames(monthly_matrix)) <- c("origin_state", "destination_state")
  attr(monthly_matrix, "row_role") <- "origin/departure"
  attr(monthly_matrix, "col_role") <- "destination/arrival"

  matrix_name <- sprintf(
    "%s%d",
    tolower(month.abb[month_value]),
    year_value
  )

  monthly_matrices[[matrix_name]] <- monthly_matrix
  cat(
    "Built", matrix_name,
    "with dimension", paste(dim(monthly_matrix), collapse = " x "),
    "using month-normalized flight frequencies\n"
  )
}

saveRDS(monthly_matrices, output_path)
cat("Saved", basename(output_path), "with", length(monthly_matrices), "matrices\n")
