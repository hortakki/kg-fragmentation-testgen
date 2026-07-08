# Documentum ID: TOOLCHAIN-CONF-RENTABLE-ITEM-01
# Description: Rentable Item Management
# Status: Effective

## 3. Rentable Item Management

## 3.1 Item Creation
## 3.1.1 The system shall allow authorized users to create rentable items.
## .1.2 The system shall require the following fields: item name, item description, and **Item ID**.
## 3.1.3 The **Item ID** must be a unique 8-character alphanumeric string.
## 3.1.4 The system shall store the item with status set to Available or Unavailable.

## 3.2 Item Modification
## 3.2.1 The system shall allow authorized users to modify item details.
## 3.2.2 The system shall validate all required fields before saving modifications.
## 3.2.3 The system shall prevent unauthorized users from modifying item data.

## 3.3 Item Availability Status
## 3.3.1 The system shall allow authorized users to set item availability status.
## 3.3.2 The system shall prevent items marked as Unavailable from being rented.
## 3.3.3 The system shall ensure availability status changes take effect immediately.

## 3.4 Item Deletion
## 3.4.1 The system shall allow authorized users to delete items.
## 3.4.2 The system shall prevent deletion of items that have Active rent records.
## 3.4.3 The system shall mark deleted items as Inactive instead of permanently removing them, unless explicitly configured otherwise.

## 3.5 Item Access Control
## 3.5.1 The system shall allow all authenticated users to view available items.
## 3.5.2 The system shall restrict item creation, modification, and deletion to authorized users.