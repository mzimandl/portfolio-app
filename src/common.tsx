import React from "react";

export interface Config {
    base_currency: string;
    language_locale: string;
}

export function numberIsValid(value: string): boolean {
    return !isNaN(Number(value));
}

export interface SectionProps {
    config: Config;
    setHeading: (name:string) => void;
    displayProgressBar: (isBusy: boolean) => void;
}

export interface SectionState {}

export abstract class AbstractSection<P = {}, S = {}, SS = {}> extends React.Component<P & SectionProps, S & SectionState, SS> {

    abstract sectionName():string;

    componentDidMount() {
        this.props.setHeading(this.sectionName());
    }

    formatCurrency(value: number, options?: {currency?: string, signed?: boolean}): string|null {
        if (value && (this.props.config.base_currency || options?.currency))
            return value.toLocaleString(
                this.props.config.language_locale,
                {
                    style: 'currency',
                    currency: options?.currency ? options?.currency : this.props.config.base_currency,
                    signDisplay: options?.signed ? "exceptZero" : "auto",
                }
            );
        return null;
    }

    formatPercents(value: number): string|null {
        if (value)
            return value.toLocaleString(
                this.props.config.language_locale,
                {
                    style: 'percent', minimumFractionDigits: 1
                }
            );
        return null;
    }
}