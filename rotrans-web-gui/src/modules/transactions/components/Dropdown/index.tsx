import React, { useState } from "react";
import { KeyInterface } from "../../interfaces/KeyInterface";

import "./styles.css";

interface ListItemProps {
  label: string;
  onClick: (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => void;
  selected: boolean;
}

interface DropdownProps {
  isOpen: boolean;
  onSelection: Function;
  options: KeyInterface[];
}

const ListItem: React.FC<ListItemProps> = ({ label, onClick, selected }) => (
  <div
    className={
      selected
        ? "dropdown-list-item dropdown-list-item-selected"
        : "dropdown-list-item"
    }
    onClick={onClick}
  >
    {label}
  </div>
);

const Dropdown: React.FC<DropdownProps> = ({
  isOpen,
  onSelection,
  options,
}) => {
  const [selectedOption, setSelectedOption] = useState(options.length - 1);

  const onOptionClicked = (selectedIndex) => {
    setSelectedOption(selectedIndex);
    onSelection(selectedIndex);
  };

  return (
    <div className="dropdown-container">
      {isOpen && (
        <div className="dropdown-list">
          <div className="dropdown-list-item">
            {options.map((item, index) => (
              <ListItem
                label={item.public_key}
                onClick={() => onOptionClicked(index)}
                selected={selectedOption === index}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dropdown;
