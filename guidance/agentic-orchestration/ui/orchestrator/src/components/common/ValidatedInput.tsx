// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useEffect } from 'react';
import { Input, FormField, InputProps } from '@cloudscape-design/components';
import { ValidationError } from '../../utils/errorHandling';

interface ValidatedInputProps extends Omit<InputProps, 'onChange' | 'value'> {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  description?: string;
  required?: boolean;
  validator?: (value: string) => void;
  validateOnBlur?: boolean;
  validateOnChange?: boolean;
  errorText?: string;
  onKeyDown?: (event: React.KeyboardEvent) => void;
}

/**
 * Input component with built-in validation and error display
 * Provides consistent validation behavior and error messaging
 */
const ValidatedInput: React.FC<ValidatedInputProps> = ({
  value,
  onChange,
  label,
  description,
  required = false,
  validator,
  validateOnBlur = true,
  validateOnChange = false,
  errorText: externalErrorText,
  onKeyDown,
  ...inputProps
}) => {
  const [internalError, setInternalError] = useState<string>('');
  const [touched, setTouched] = useState(false);

  const validate = (valueToValidate: string) => {
    try {
      // Check required field
      if (required && !valueToValidate.trim()) {
        throw new ValidationError(`${label || 'This field'} is required`);
      }

      // Run custom validator
      if (validator && valueToValidate.trim()) {
        validator(valueToValidate);
      }

      setInternalError('');
    } catch (error) {
      if (error instanceof ValidationError) {
        setInternalError(error.message);
      } else {
        setInternalError('Invalid input');
      }
    }
  };

  const handleChange = (event: any) => {
    const newValue = event.detail.value;
    onChange(newValue);

    if (validateOnChange && touched) {
      validate(newValue);
    }
  };

  const handleBlur = () => {
    setTouched(true);
    if (validateOnBlur) {
      validate(value);
    }
  };

  // Validate when external dependencies change
  useEffect(() => {
    if (touched && (validateOnChange || validateOnBlur)) {
      validate(value);
    }
  }, [value, validator, required, touched, validateOnChange, validateOnBlur]);

  const errorText = externalErrorText || internalError;

  return (
    <FormField
      label={label}
      description={description}
      errorText={errorText}
    >
      <Input
        {...inputProps} // nosemgrep: react-props-spreading
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        onKeyDown={(event) => {
          if (onKeyDown) {
            // Cloudscape Input uses event.detail for key information
            const syntheticEvent = {
              ...event,
              key: event.detail?.key,
              shiftKey: event.detail?.shiftKey,
              preventDefault: () => event.preventDefault?.(),
              stopPropagation: () => event.stopPropagation?.()
            } as any;
            onKeyDown(syntheticEvent);
          }
        }}
        invalid={!!errorText}
        ariaRequired={required}
      />
    </FormField>
  );
};

export default ValidatedInput;