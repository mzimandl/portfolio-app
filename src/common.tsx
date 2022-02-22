import React from "react";

export interface Config {
    base_currency: string;
    language_locale: string;
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

    formatCurrency(value: number, currency?: string): string|null {
        if (value && (this.props.config.base_currency || currency))
            return value.toLocaleString(this.props.config.language_locale, {style: 'currency', currency: currency ? currency : this.props.config.base_currency});
        return null;
    }

    formatPercents(value: number): string|null {
        if (value)
            return value.toLocaleString(this.props.config.language_locale, {style: 'percent', minimumFractionDigits: 1});
        return null;
    }
}