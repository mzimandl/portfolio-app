import React from "react";


export interface SectionProps {
    setHeading: (name:string) => void;
    displayProgressBar: (isBusy: boolean) => void;
}

export interface SectionState {
    base_currency?: string;
}

export abstract class AbstractSection<P = {}, S = {}, SS = {}> extends React.Component<P & SectionProps, S & SectionState, SS> {

    abstract sectionName():string;

    componentDidMount() {
        this.props.setHeading(this.sectionName());
    }

    formatCurrency(value: number, currency?: string): string|null {
        if (value && (this.state.base_currency || currency))
            return value.toLocaleString(undefined, {style: 'currency', currency: currency ? currency : this.state.base_currency});
        return null;
    }

    formatPercents(value: number): string|null {
        if (value)
            return value.toLocaleString(undefined, {style: 'percent', minimumFractionDigits: 1});
        return null;
    }
}