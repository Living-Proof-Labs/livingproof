# SPDX-License-Identifier: Apache-2.0
Feature: Use the installed Living Proof Labs command home
  These examples run packaged wheels in fresh containers with networking disabled.
  The reporting image includes the explicitly selected release in reporter-release.txt.

  Scenario: Root help teaches the available command families
    Given the root-only installed image
    When I run "livingproof --help"
    Then the exit status is 0
    And the output contains "capability"
    And the output contains "plugins"
    And the output contains "livingproof completion status"

  Scenario: Missing reporting plugin explains an explicit next step
    Given the root-only installed image
    When I run "livingproof capability report --help"
    Then the exit status is 1
    And the output contains "livingproof plugins install livingproof-capability-report"
    And the output contains "No packages are installed automatically"
    When I run "livingproof plugins install --help"
    Then the exit status is 0
    And the output contains "--version"

  Scenario: Installed root discovers the reporting plugin
    Given the reporting installed image
    When I run "livingproof plugins status livingproof-capability-report"
    Then the exit status is 0
    And the output contains "livingproof-capability-report"
    When I run "livingproof capability report --help"
    Then the exit status is 0
    And the output contains "validate"
    And the output contains "grade"
    And the output contains "render"

  Scenario: Installed root validates a published example bundle
    Given the reporting installed image
    When I run "livingproof capability report validate /input/manifest.json"
    Then the exit status is 0
    And the output contains "Valid bundle structure"

  Scenario: Missing manifest fails with useful command usage
    Given the reporting installed image
    When I run "livingproof capability report validate /input/missing.json"
    Then the exit status is 2
    And the output contains "Usage:"
    And the output contains "--help"
    And the output contains "does not exist"
