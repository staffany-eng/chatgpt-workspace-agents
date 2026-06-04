#!/usr/bin/env ruby
# frozen_string_literal: true

require "date"
require "set"
require "yaml"

ROOT = File.expand_path("../../indonesia-payroll-tax-advisor/references", __dir__)
REGULATIONS = File.join(ROOT, "regulations.yml")
EXPECTED_REFERENCES = %w[
  pph21.md
  reporting.md
  source-quality.md
].freeze

REQUIRED_SOURCE_FIELDS = %w[
  id
  title
  publisher
  regulator_type
  url
  effective_period
  last_checked
  topics
  status
  confidence
  notes
].freeze

VALID_CONFIDENCE = %w[high medium low].freeze
VALID_STATUS = %w[active historical placeholder superseded seeded].freeze

def fail_with(message)
  warn "ERROR: #{message}"
  exit 1
end

fail_with("Missing regulations.yml at #{REGULATIONS}") unless File.file?(REGULATIONS)

EXPECTED_REFERENCES.each do |name|
  path = File.join(ROOT, name)
  fail_with("Missing expected reference file #{path}") unless File.file?(path)
end

data = YAML.load_file(REGULATIONS)
sources = data.fetch("sources") { fail_with("regulations.yml must contain a sources list") }
fail_with("sources must be an array") unless sources.is_a?(Array)

ids = Set.new
errors = []

sources.each_with_index do |source, index|
  label = source["id"] || "source at index #{index}"

  REQUIRED_SOURCE_FIELDS.each do |field|
    value = source[field]
    if value.nil? || (value.respond_to?(:empty?) && value.empty?)
      errors << "#{label}: missing #{field}"
    end
  end

  if source["id"] && !ids.add?(source["id"])
    errors << "#{label}: duplicate id"
  end

  if source["last_checked"]
    begin
      Date.iso8601(source["last_checked"])
    rescue ArgumentError
      errors << "#{label}: last_checked must be YYYY-MM-DD"
    end
  end

  if source["confidence"] && !VALID_CONFIDENCE.include?(source["confidence"])
    errors << "#{label}: confidence must be one of #{VALID_CONFIDENCE.join(', ')}"
  end

  if source["status"] && !VALID_STATUS.include?(source["status"])
    errors << "#{label}: status must be one of #{VALID_STATUS.join(', ')}"
  end

  if source["topics"] && (!source["topics"].is_a?(Array) || source["topics"].empty?)
    errors << "#{label}: topics must be a non-empty array"
  end

  if source["url"] && source["url"] !~ %r{\Ahttps?://}
    errors << "#{label}: url must start with http:// or https://"
  end
end

if errors.any?
  warn errors.map { |error| "ERROR: #{error}" }.join("\n")
  exit 1
end

puts "Knowledge bank OK: #{sources.length} sources checked."
